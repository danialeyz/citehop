"""Run a trusted local SQL file statement by statement: python -m citehop.apply_sql sql/x.sql

No browser-facing SQL endpoint.

DDL implicitly commits in MariaDB. This is not an atomic migration runner.
Stored procedures / client DELIMITER directives are deliberately unsupported.
"""
import argparse
from pathlib import Path

import sqlparse

from citehop.db import connect


def statements(source):
    if any(line.strip().upper().startswith("DELIMITER") for line in source.splitlines()):
        raise ValueError("DELIMITER scripts require the mariadb CLI")
    # Comment-only pieces (e.g. a trailing comment) would fail as empty queries.
    return [query for query in sqlparse.split(source, strip_semicolon=True)
            if sqlparse.format(query, strip_comments=True).strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    queries = statements(args.file.read_text(encoding="utf-8"))
    with connect() as connection:
        cursor = connection.cursor()
        for i, query in enumerate(queries, 1):
            cursor.execute(query)
            label = sqlparse.format(query, strip_comments=True).strip().splitlines()[0]
            print(f"[{i}/{len(queries)}] ok: {label[:70]}")
            if cursor.description:
                for row in cursor:
                    print(row)
        connection.commit()
    print(f"Applied {len(queries)} statements")


if __name__ == "__main__":
    main()
