"""Explicit local C01 acceptance check; writes only unique smoke records.

Run with .venv/bin/python scripts/check_persistence.py from repository root.
Restarts this checkout's Compose services; never removes volumes.
"""
import subprocess
import sys
import uuid

from citehop.db import connect, graph_driver


def drop_table(table):
    with connect() as connection:
        connection.cursor().execute(f"DROP TABLE IF EXISTS {table}")


def delete_node(token):
    with graph_driver() as driver:
        driver.execute_query("MATCH (n:C01Smoke {token: $token}) DELETE n", token=token)


def main():
    token = uuid.uuid4().hex
    table = f"c01_smoke_{token}"  # generated identifier, never user SQL
    compose = ["docker", "compose", "--env-file", ".env", "-f", "docker/docker-compose.yml"]
    try:
        with connect() as connection:
            cursor = connection.cursor()
            cursor.execute(f"CREATE TABLE {table} (id VARCHAR(32) PRIMARY KEY)")
            cursor.execute(f"INSERT INTO {table} VALUES (?)", (token,))
            connection.commit()
        with graph_driver() as driver:
            driver.execute_query("CREATE (:C01Smoke {token: $token})", token=token)
        subprocess.run([*compose, "restart"], check=True)
        subprocess.run([*compose, "up", "-d", "--wait"], check=True)
        with connect() as connection:
            cursor = connection.cursor()
            cursor.execute(f"SELECT id FROM {table}")
            assert cursor.fetchone() == (token,)
        with graph_driver() as driver:
            records, _, _ = driver.execute_query(
                "MATCH (n:C01Smoke {token: $token}) RETURN n.token AS token", token=token
            )
            assert len(records) == 1 and records[0]["token"] == token
        print("PASS: MariaDB row and Neo4j node survived restart")
    finally:
        # Only this invocation's generated table/node can be removed. Each step is
        # independent and never masks the original error.
        for name, cleanup, target in (("MariaDB table", drop_table, table),
                                      ("Neo4j node", delete_node, token)):
            try:
                cleanup(target)
            except Exception as error:
                print(f"WARNING: could not remove {name} {target}: "
                      f"{type(error).__name__}", file=sys.stderr)


if __name__ == "__main__":
    main()
