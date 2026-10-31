"""Read the graph-relevant MariaDB snapshot: articles, categories, and article links.

MariaDB is the source of truth (schema: sql/corpus_schema.sql, docs/DATA_MODEL.md). The
corpus version is the latest `corpus_versions.version_id`, which the C03 loader advances on
any content change. Only the statements below touch MariaDB.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

ARTICLES_SQL = "SELECT article_id, title, source_url, revision_id FROM articles"
CATEGORIES_SQL = "SELECT article_id, category_name FROM article_categories"
LINKS_SQL = "SELECT source_article_id, target_article_id FROM article_links"
VERSION_SQL = "SELECT MAX(version_id) FROM corpus_versions"


@dataclass(frozen=True)
class Article:
    article_id: int | str
    title: str
    source_url: str
    revision_id: int | str | None


@dataclass(frozen=True)
class Snapshot:
    """A deduplicated, sorted, orphan-free view of the corpus graph."""

    articles: tuple[Article, ...]
    categories: tuple[str, ...]
    memberships: tuple[tuple[int | str, str], ...]
    links: tuple[tuple[int | str, int | str], ...]
    skipped_links: int
    skipped_memberships: int
    corpus_version: str | None = None

    @property
    def version(self) -> str:
        """MariaDB corpus version when read from MariaDB, else a fingerprint of the content."""
        if self.corpus_version:
            return self.corpus_version
        payload = json.dumps(
            [
                [[a.article_id, a.title, a.source_url, a.revision_id] for a in self.articles],
                self.memberships,
                self.links,
            ],
            separators=(",", ":"),
            default=str,
        )
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]

    def counts(self) -> dict[str, int]:
        return {
            "articles": len(self.articles),
            "categories": len(self.categories),
            "links": len(self.links),
            "memberships": len(self.memberships),
        }


def _key(value):
    return (isinstance(value, str), value)


def build_snapshot(article_rows, category_rows, link_rows, corpus_version=None) -> Snapshot:
    """Normalize raw rows; links/memberships to missing articles are skipped and counted."""
    articles = {}
    for article_id, title, source_url, revision_id in article_rows:
        if article_id in articles:
            raise ValueError(f"duplicate article_id {article_id!r} in source")
        articles[article_id] = Article(article_id, title, source_url, revision_id)

    memberships, skipped_memberships = set(), 0
    for article_id, category in category_rows:
        name = (category or "").strip()
        if article_id in articles and name:
            memberships.add((article_id, name))
        else:
            skipped_memberships += 1

    links, skipped_links = set(), 0
    for source_id, target_id in link_rows:
        if source_id in articles and target_id in articles:
            links.add((source_id, target_id))
        else:
            skipped_links += 1

    return Snapshot(
        articles=tuple(articles[k] for k in sorted(articles, key=_key)),
        categories=tuple(sorted({name for _, name in memberships})),
        memberships=tuple(sorted(memberships, key=lambda m: (_key(m[0]), m[1]))),
        links=tuple(sorted(links, key=lambda e: (_key(e[0]), _key(e[1])))),
        skipped_links=skipped_links,
        skipped_memberships=skipped_memberships,
        corpus_version=corpus_version,
    )


def corpus_version(cur) -> str:
    """Current corpus version, e.g. `corpus:2`. One indexed row lookup; cheap to call often."""
    cur.execute(VERSION_SQL)
    (version_id,) = cur.fetchone()
    if version_id is None:
        raise ValueError("corpus_versions is empty; run python -m citehop.corpus first")
    return f"corpus:{version_id}"


def read_corpus_version(conn) -> str:
    cur = conn.cursor()
    try:
        return corpus_version(cur)
    finally:
        cur.close()


def read_snapshot(conn) -> Snapshot:
    """Read the version and graph tables in one transaction, so they describe the same load.

    InnoDB's default REPEATABLE READ gives every read in the transaction the same snapshot.
    """
    cur = conn.cursor()
    try:
        version = corpus_version(cur)
        cur.execute(ARTICLES_SQL)
        article_rows = cur.fetchall()
        cur.execute(CATEGORIES_SQL)
        category_rows = cur.fetchall()
        cur.execute(LINKS_SQL)
        link_rows = cur.fetchall()
    finally:
        cur.close()
        conn.rollback()  # read-only; end the snapshot transaction
    return build_snapshot(article_rows, category_rows, link_rows, corpus_version=version)
