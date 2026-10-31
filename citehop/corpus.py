"""Load a C02 Wikipedia snapshot into MariaDB in one transaction.

The snapshot replaces the corpus: articles absent from it are deleted (cascading to their
categories, links and chunks). A changed revision deletes that article's chunks/embeddings.
Any content change appends a new corpus_versions row; an identical rerun changes nothing.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

REQUIRED = ("article_id", "title", "revision_id", "source_url", "revision_url", "text",
            "text_sha256", "length_chars", "categories", "internal_links", "provenance")
ARTICLE_COLUMNS = ("article_id", "title", "revision_id", "revision_timestamp", "source_url",
                   "revision_url", "text", "text_sha256", "length_chars", "is_smoke",
                   "license_url", "attribution")
# Columns compared to decide whether an existing article row needs rewriting.
COMPARED = ("title", "revision_id", "source_url", "revision_url", "text_sha256", "is_smoke",
            "license_url", "attribution")


def batches(rows, size):
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def timestamp(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def prepare(snapshot, manifest):
    """Validate a snapshot against its manifest and resolve links by exact title.

    Returns (articles, categories, links, subset, report). Link titles absent from the snapshot
    (other Wikipedia pages, unresolved redirects) are counted as orphans and not stored.
    """
    if snapshot.get("corpus_id") != manifest["corpus_id"]:
        raise ValueError("snapshot corpus_id does not match manifest")
    pins = {pin["article_id"]: pin for pin in manifest["articles"]}
    records = snapshot["articles"]
    ids = [record.get("article_id") for record in records]
    if not records or len(set(ids)) != len(ids):
        raise ValueError("snapshot must contain distinct article_id values")
    if set(ids) == set(pins):
        subset = "full"
    elif set(ids) == {aid for aid, pin in pins.items() if pin["smoke"]}:
        subset = "smoke"
    else:
        raise ValueError("snapshot is neither the full nor the smoke subset of the manifest")

    by_title = {}
    for record in records:
        missing = [key for key in REQUIRED if key not in record]
        if missing:
            raise ValueError(f"{record.get('title', '?')}: missing {missing}")
        if record["revision_id"] != pins[record["article_id"]]["revision_id"]:
            raise ValueError(f"{record['title']}: revision differs from manifest pin")
        text = record["text"]
        if not text or hashlib.sha256(text.encode()).hexdigest() != record["text_sha256"]:
            raise ValueError(f"{record['title']}: text hash mismatch")
        if record["length_chars"] != len(text):
            raise ValueError(f"{record['title']}: length_chars mismatch")
        if record["title"] in by_title:
            raise ValueError(f"duplicate title: {record['title']}")
        by_title[record["title"]] = record["article_id"]

    articles, categories, links = [], set(), set()
    report = {"orphan_links": 0, "self_links": 0, "duplicate_categories": 0}
    for record in sorted(records, key=lambda r: r["article_id"]):
        aid, provenance = record["article_id"], record["provenance"]
        pin = pins[aid]
        articles.append({
            "article_id": aid, "title": record["title"], "revision_id": record["revision_id"],
            "revision_timestamp": timestamp(pin.get("revision_timestamp")),
            "source_url": record["source_url"], "revision_url": record["revision_url"],
            "text": record["text"], "text_sha256": record["text_sha256"],
            "length_chars": record["length_chars"], "is_smoke": bool(pin["smoke"]),
            "license_url": provenance["license_url"], "attribution": provenance["attribution"],
        })
        names = [" ".join(name.split()) for name in record["categories"]]
        clean = {name for name in names if name}
        report["duplicate_categories"] += len(names) - len(clean)
        categories |= {(aid, name) for name in clean}
        for title in set(record["internal_links"]):
            target = by_title.get(title)
            if target is None:
                report["orphan_links"] += 1
            elif target == aid:
                report["self_links"] += 1
            else:
                links.add((aid, target))
    return articles, sorted(categories), sorted(links), subset, report


def content_hash(articles, categories, links):
    """Identity of loaded content; the load time and manifest ID are excluded."""
    keys = [[a[column] for column in ("article_id",) + COMPARED] for a in articles]
    payload = json.dumps([keys, categories, links], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def load(connection, snapshot, manifest, batch_size=500):
    """Reconcile MariaDB with the snapshot inside one transaction and return a report."""
    articles, categories, links, subset, report = prepare(snapshot, manifest)
    digest = content_hash(articles, categories, links)
    cursor = connection.cursor()
    try:
        connection.begin()
        cursor.execute("SELECT article_id, " + ", ".join(COMPARED) + " FROM articles FOR UPDATE")
        existing = {row[0]: dict(zip(COMPARED, row[1:], strict=True)) for row in cursor}
        for row in existing.values():
            row["is_smoke"] = bool(row["is_smoke"])
        wanted = {a["article_id"]: a for a in articles}
        removed = sorted(set(existing) - set(wanted))
        changed = sorted(aid for aid in set(existing) & set(wanted)
                         if existing[aid]["revision_id"] != wanted[aid]["revision_id"])
        stale = [a for a in articles if a["article_id"] not in existing
                 or any(existing[a["article_id"]][c] != a[c] for c in COMPARED)]

        cursor.execute("SELECT article_id, category_name FROM article_categories")
        old_categories = set(cursor.fetchall())
        cursor.execute("SELECT source_article_id, target_article_id FROM article_links")
        old_links = set(cursor.fetchall())

        # Chunks of changed revisions or removed articles go first: their embeddings were
        # computed from text that is no longer current. The FK would otherwise block the update.
        invalidated = 0
        for group in batches(changed + removed, batch_size):
            marks = ", ".join("?" * len(group))
            cursor.execute(f"DELETE FROM chunks WHERE article_id IN ({marks})", tuple(group))
            invalidated += cursor.rowcount
        drop_links = sorted(old_links - set(links))
        drop_categories = sorted(old_categories - set(categories))
        for group in batches(drop_links, batch_size):
            cursor.executemany("DELETE FROM article_links WHERE source_article_id = ? "
                               "AND target_article_id = ?", group)
        for group in batches(drop_categories, batch_size):
            cursor.executemany("DELETE FROM article_categories WHERE article_id = ? "
                               "AND category_name = ?", group)
        for group in batches(removed, batch_size):
            marks = ", ".join("?" * len(group))
            cursor.execute(f"DELETE FROM articles WHERE article_id IN ({marks})", tuple(group))

        # Titles may move between page IDs across snapshots. Park every renamed row under a
        # placeholder first ('<' and '>' cannot occur in Wikipedia titles), then update by
        # primary key and insert new IDs separately, so no write can hit another row's title.
        renamed = [aid for aid in sorted(set(existing) & set(wanted))
                   if existing[aid]["title"] != wanted[aid]["title"]]
        for group in batches(renamed, batch_size):
            cursor.executemany("UPDATE articles SET title = ? WHERE article_id = ?",
                               [(f"<renaming {aid}>", aid) for aid in group])
        update = ("UPDATE articles SET " + ", ".join(f"{c} = ?" for c in ARTICLE_COLUMNS[1:])
                  + " WHERE article_id = ?")
        insert = (f"INSERT INTO articles ({', '.join(ARTICLE_COLUMNS)}) "
                  f"VALUES ({', '.join('?' * len(ARTICLE_COLUMNS))})")
        updates = [a for a in stale if a["article_id"] in existing]
        inserts = [a for a in stale if a["article_id"] not in existing]
        # Article text can be large; keep each bulk packet well below max_allowed_packet.
        for group in batches(updates, min(batch_size, 25)):
            cursor.executemany(update, [tuple(a[c] for c in ARTICLE_COLUMNS[1:])
                                        + (a["article_id"],) for a in group])
        for group in batches(inserts, min(batch_size, 25)):
            cursor.executemany(insert, [tuple(a[c] for c in ARTICLE_COLUMNS) for a in group])
        add_categories = sorted(set(categories) - old_categories)
        add_links = sorted(set(links) - old_links)
        for group in batches(add_categories, batch_size):
            cursor.executemany("INSERT INTO article_categories (article_id, category_name) "
                               "VALUES (?, ?)", group)
        for group in batches(add_links, batch_size):
            cursor.executemany("INSERT INTO article_links (source_article_id, target_article_id) "
                               "VALUES (?, ?)", group)

        cursor.execute("SELECT version_id, content_sha256 FROM corpus_versions "
                       "ORDER BY version_id DESC LIMIT 1 FOR UPDATE")
        latest = cursor.fetchone()
        advanced = latest is None or latest[1] != digest
        if advanced:
            cursor.execute(
                "INSERT INTO corpus_versions (content_sha256, source_corpus_id, subset, "
                "article_count, category_count, link_count) VALUES (?, ?, ?, ?, ?, ?)",
                (digest, manifest["corpus_id"], subset, len(articles),
                 len({name for _, name in categories}), len(links)))
            version_id = cursor.lastrowid
        else:
            version_id = latest[0]
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
    report.update({
        "corpus_version": version_id, "version_advanced": advanced, "content_sha256": digest,
        "subset": subset, "articles": len(articles), "category_memberships": len(categories),
        "distinct_categories": len({name for _, name in categories}), "links": len(links),
        "articles_written": len(stale), "articles_renamed": len(renamed),
        "articles_removed": len(removed),
        "revisions_changed": len(changed), "chunks_invalidated": invalidated,
        "categories_added": len(add_categories), "categories_removed": len(drop_categories),
        "links_added": len(add_links), "links_removed": len(drop_links),
    })
    return report


def counts(connection):
    """Live row counts plus the current corpus version."""
    cursor = connection.cursor()
    result = {}
    for table in ("articles", "article_categories", "article_links", "chunks"):
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        result[table] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT category_name) FROM article_categories")
    result["distinct_categories"] = cursor.fetchone()[0]
    cursor.execute("SELECT MAX(version_id) FROM corpus_versions")
    result["corpus_version"] = cursor.fetchone()[0]
    cursor.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default="data/wikipedia/smoke.json", type=Path)
    parser.add_argument("--manifest", default="eval/corpus.json", type=Path)
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    from citehop.db import connect  # C01 helper; lazy so unit tests need no driver

    try:
        snapshot = json.loads(args.snapshot.read_text())
        manifest = json.loads(args.manifest.read_text())
        with connect() as connection:
            report = load(connection, snapshot, manifest, args.batch_size)
            report["live_counts"] = counts(connection)
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
