"""Graph CLI. Import is explicit and manual; nothing syncs in the background.

    python -m citehop.graph import [--batch-size N]
    python -m citehop.graph status
    python -m citehop.graph neighborhood ARTICLE_ID [--hops 1|2] [--max-nodes N] [--max-edges N]
                                         [--links-only | --categories-only]
    python -m citehop.graph path SOURCE_ID TARGET_ID [--undirected]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict

from dotenv import load_dotenv


def mariadb_connect():
    import mariadb

    return mariadb.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "citehop"),
        password=os.getenv("DB_PASS", ""),
        database=os.getenv("DB_NAME", "citehop"),
        connect_timeout=5,
    )


def neo4j_driver():
    from neo4j import GraphDatabase

    return GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "")),
        connection_timeout=5,
        max_transaction_retry_time=2,  # an outage reports `unavailable` quickly, not after 30s
    )


def source_version() -> str | None:
    """Fingerprint of MariaDB's graph tables (a full read); GraphQueries caches it."""
    from citehop.graph.source import read_snapshot

    conn = mariadb_connect()
    try:
        return read_snapshot(conn).version
    finally:
        conn.close()


def _article_id(value: str):
    # Stable IDs come from MariaDB; numeric IDs arrive as strings on the command line.
    return int(value) if value.isdigit() else value


def main(argv=None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="python -m citehop.graph")
    sub = parser.add_subparsers(dest="cmd", required=True)
    imp = sub.add_parser("import", help="rebuild the Neo4j graph from MariaDB")
    imp.add_argument("--batch-size", type=int, default=500)
    sub.add_parser("status", help="report ready/stale/rebuilding/unavailable")
    nb = sub.add_parser("neighborhood", help="bounded neighborhood of one article")
    nb.add_argument("article_id", type=_article_id)
    nb.add_argument("--hops", type=int, default=1)
    nb.add_argument("--max-nodes", type=int, default=50)
    nb.add_argument("--max-edges", type=int, default=100)
    only = nb.add_mutually_exclusive_group()
    only.add_argument("--links-only", action="store_true")
    only.add_argument("--categories-only", action="store_true")
    pt = sub.add_parser("path", help="shortest LINKS_TO path within 3 links")
    pt.add_argument("source_id", type=_article_id)
    pt.add_argument("target_id", type=_article_id)
    pt.add_argument("--undirected", action="store_true")
    args = parser.parse_args(argv)

    from citehop.graph.queries import GraphQueries
    from citehop.graph.source import read_snapshot
    from citehop.graph.store import GraphError, import_snapshot

    driver = neo4j_driver()
    try:
        if args.cmd == "import":
            conn = mariadb_connect()
            try:
                snapshot = read_snapshot(conn)
            finally:
                conn.close()
            out = asdict(import_snapshot(driver, snapshot, batch_size=args.batch_size))
        else:
            graph = GraphQueries(driver, source_version)
            if args.cmd == "status":
                out = asdict(graph.status())
            elif args.cmd == "neighborhood":
                types = ("LINKS_TO",) if args.links_only else (
                    ("IN_CATEGORY",) if args.categories_only else ("LINKS_TO", "IN_CATEGORY"))
                out = graph.neighborhood(args.article_id, hops=args.hops,
                                         max_nodes=args.max_nodes, max_edges=args.max_edges,
                                         rel_types=types)
            else:
                out = graph.path(args.source_id, args.target_id, directed=not args.undirected)
    except (GraphError, ValueError) as exc:
        print(json.dumps({"error": type(exc).__name__, "detail": str(exc)}), file=sys.stderr)
        return 1
    finally:
        driver.close()
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
