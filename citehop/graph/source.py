"""Read the graph-relevant MariaDB snapshot: articles, categories, and article links.

MariaDB is the source of truth. The column names below follow the shared-contract table
names (articles, article_categories, article_links); confirm them against the C03 data
model before the first real import. Only these three statements touch MariaDB.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

ARTICLES_SQL = "SELECT article_id, title, source_url, revision_id FROM articles"
CATEGORIES_SQL = "SELECT article_id, category FROM article_categories"
LINKS_SQL = "SELECT source_article_id, target_article_id FROM article_links"


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

    @property
    def version(self) -> str:
        """Content fingerprint of everything the graph imports; changes with any source edit."""
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


def build_snapshot(article_rows, category_rows, link_rows) -> Snapshot:
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
    )


def read_snapshot(conn) -> Snapshot:
    """Read the snapshot from any DB-API connection (MariaDB in production)."""
    cur = conn.cursor()
    try:
        cur.execute(ARTICLES_SQL)
        article_rows = cur.fetchall()
        cur.execute(CATEGORIES_SQL)
        category_rows = cur.fetchall()
        cur.execute(LINKS_SQL)
        link_rows = cur.fetchall()
    finally:
        cur.close()
    return build_snapshot(article_rows, category_rows, link_rows)
