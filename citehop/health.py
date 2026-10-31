"""Read-only readiness probes, with redacted failures."""
from neo4j import Query

from citehop.db import connect, graph_driver


def maria_ready():
    with connect() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        return cursor.fetchone()[0] == 1


def neo_ready():
    with graph_driver() as driver:
        with driver.session() as session:
            return session.run(Query("RETURN 1 AS ok", timeout=3)).single()["ok"] == 1


def service_status():
    result = {}
    for name, probe in (("mariadb", maria_ready), ("neo4j", neo_ready)):
        try:
            result[name] = "ready" if probe() else "unavailable"
        except Exception:
            result[name] = "unavailable"
    return result
