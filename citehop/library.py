"""Read-only MariaDB access for article browsing, stored passages, and answer evidence.

Every statement is parameterized and bounded by LIMIT. Passages come from `chunks` pinned to
the article's current revision (composite foreign key), so a chunk ID that resolves here is
current for the corpus version read in the same connection.
"""

from __future__ import annotations

from citehop.graph.source import read_corpus_version

MAX_PAGE_SIZE = 100
MAX_PASSAGE_PAGE_SIZE = 50
MAX_TITLE_FILTER_CHARS = 200
MAX_CATEGORIES_PER_ITEM = 50


def _like_pattern(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped.lower()}%"


def article_filters(title=None, category=None):
    clauses, params = [], []
    if title:
        clauses.append("LOWER(a.title) LIKE ?")
        params.append(_like_pattern(title))
    if category:
        clauses.append("EXISTS (SELECT 1 FROM article_categories ac "
                       "WHERE ac.article_id = a.article_id AND ac.category_name = ?)")
        params.append(category)
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def _categories(cursor, article_ids):
    if not article_ids:
        return {}
    marks = ", ".join("?" for _ in article_ids)
    cursor.execute(f"SELECT article_id, category_name FROM article_categories "
                   f"WHERE article_id IN ({marks}) ORDER BY article_id, category_name",
                   tuple(article_ids))
    result = {i: [] for i in article_ids}
    for article_id, name in cursor.fetchall():
        result[article_id].append(name)
    return result


def list_articles(connection, *, title=None, category=None, page=1, page_size=20) -> dict:
    """One page of articles ordered by title, the filtered total, and the corpus version."""
    if not 1 <= page_size <= MAX_PAGE_SIZE or page < 1:
        raise ValueError("invalid page or page_size")
    where, params = article_filters(title, category)
    cursor = connection.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM articles a{where}", tuple(params))
    (total,) = cursor.fetchone()
    cursor.execute(
        "SELECT a.article_id, a.title, a.source_url, a.length_chars, "
        "(SELECT COUNT(*) FROM chunks c WHERE c.article_id = a.article_id "
        " AND c.revision_id = a.revision_id) AS chunks "
        f"FROM articles a{where} ORDER BY a.title, a.article_id LIMIT ? OFFSET ?",
        (*params, page_size, (page - 1) * page_size))
    rows = cursor.fetchall()
    categories = _categories(cursor, [r[0] for r in rows])
    cursor.close()
    items = [{"article_id": int(r[0]), "title": r[1], "source_url": r[2],
              "length_chars": int(r[3]), "chunk_count": int(r[4]),
              "categories": categories[r[0]][:MAX_CATEGORIES_PER_ITEM]} for r in rows]
    return {"items": items, "total": int(total), "page": page, "page_size": page_size,
            "corpus_version": read_corpus_version(connection)}


ARTICLE_SQL = (
    "SELECT article_id, title, revision_id, revision_timestamp, source_url, revision_url, "
    "length_chars, is_smoke, license_url, attribution FROM articles WHERE article_id = ?")

# The newest embedding configuration that has chunks for this article and revision.
PASSAGE_CONFIG_SQL = (
    "SELECT ec.chunk_config, ec.embedding_config FROM embedding_configs ec "
    "WHERE EXISTS (SELECT 1 FROM chunks c WHERE c.embedding_config = ec.embedding_config "
    "AND c.chunk_config = ec.chunk_config AND c.article_id = ? AND c.revision_id = ?) "
    "ORDER BY ec.created_at DESC, ec.embedding_config LIMIT 1")


def article_detail(connection, article_id: int, *, passage_page=1,
                   passage_page_size=20) -> dict | None:
    """Metadata, categories, link counts, and one page of stored passages; None if missing."""
    if not 1 <= passage_page_size <= MAX_PASSAGE_PAGE_SIZE or passage_page < 1:
        raise ValueError("invalid passage_page or passage_page_size")
    cursor = connection.cursor()
    cursor.execute(ARTICLE_SQL, (article_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.close()
        return None
    names = ("article_id", "title", "revision_id", "revision_timestamp", "source_url",
             "revision_url", "length_chars", "is_smoke", "license_url", "attribution")
    article = dict(zip(names, row, strict=True))
    article["is_smoke"] = bool(article["is_smoke"])
    if article["revision_timestamp"] is not None:
        article["revision_timestamp"] = article["revision_timestamp"].isoformat() + "Z"
    article["categories"] = _categories(cursor, [article_id])[article_id]
    cursor.execute("SELECT (SELECT COUNT(*) FROM article_links WHERE source_article_id = ?), "
                   "(SELECT COUNT(*) FROM article_links WHERE target_article_id = ?)",
                   (article_id, article_id))
    outgoing, incoming = cursor.fetchone()
    article["links"] = {"outgoing": int(outgoing), "incoming": int(incoming)}

    cursor.execute(PASSAGE_CONFIG_SQL, (article_id, article["revision_id"]))
    config = cursor.fetchone()
    passages, total = [], 0
    if config:
        scope = ("FROM chunks WHERE article_id = ? AND revision_id = ? AND chunk_config = ? "
                 "AND embedding_config = ?")
        scope_params = (article_id, article["revision_id"], *config)
        cursor.execute(f"SELECT COUNT(*) {scope}", scope_params)
        (total,) = cursor.fetchone()
        cursor.execute(f"SELECT chunk_id, ordinal, char_start, char_end, token_count, text "
                       f"{scope} ORDER BY ordinal LIMIT ? OFFSET ?",
                       (*scope_params, passage_page_size, (passage_page - 1) * passage_page_size))
        passages = [dict(zip(("chunk_id", "ordinal", "char_start", "char_end", "token_count",
                              "text"), r, strict=True)) for r in cursor.fetchall()]
    cursor.close()
    article["passages"] = {
        "items": passages, "total": int(total), "page": passage_page,
        "page_size": passage_page_size,
        "chunk_config": config[0] if config else None,
        "embedding_config": config[1] if config else None,
    }
    article["corpus_version"] = read_corpus_version(connection)
    return article


def resolve_chunks(connection, chunk_ids) -> tuple[list[dict], list[str]]:
    """Stored passages for `chunk_ids` in the given order, plus the IDs that do not resolve.

    Only chunks of the article's current revision resolve; browser-supplied text is never used.
    """
    ids = list(dict.fromkeys(chunk_ids))
    if not ids:
        return [], []
    marks = ", ".join("?" for _ in ids)
    cursor = connection.cursor()
    cursor.execute(
        "SELECT c.chunk_id, c.article_id, a.title, a.source_url, c.text FROM chunks c "
        "JOIN articles a ON a.article_id = c.article_id AND a.revision_id = c.revision_id "
        f"WHERE c.chunk_id IN ({marks})", tuple(ids))
    found = {r[0]: r for r in cursor.fetchall()}
    cursor.close()
    hits = [{"chunk_id": cid, "article_id": int(found[cid][1]), "title": found[cid][2],
             "source_url": found[cid][3], "passage": found[cid][4], "rank": rank,
             "score": None, "method": None}
            for rank, cid in enumerate((i for i in ids if i in found), 1)]
    return hits, [i for i in ids if i not in found]


def corpus_stats(connection) -> dict:
    """Live corpus counts and chunk coverage per stored embedding configuration."""
    from citehop.corpus import counts
    from citehop.embed import status

    live = counts(connection)
    coverage = status(connection)
    return {
        "corpus_version": read_corpus_version(connection),
        "articles": live["articles"],
        "smoke_articles": coverage["smoke_articles"],
        "distinct_categories": live["distinct_categories"],
        "category_memberships": live["article_categories"],
        "article_links": live["article_links"],
        "chunks": live["chunks"],
        "embedding_configs": [
            {"chunk_config": g["chunk_config"], "embedding_config": g["embedding_config"],
             "chunks": g["chunks"], "articles_covered": g["articles"],
             "token_count_min": g["token_count_min"], "token_count_max": g["token_count_max"]}
            for g in coverage["by_config"]
        ],
    }
