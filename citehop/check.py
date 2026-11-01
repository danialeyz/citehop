"""make check: real connections, pinned version, my.cnf settings and a tiny native-vector
check (no persistent writes). Prints OK and the server version, fails on the wrong version."""
import sys

from citehop.db import connect
from citehop.health import service_status

EXPECTED = "11.8.9"
SETTINGS = ("mhnsw_max_cache_size", "innodb_ft_min_token_size")


def main():
    status = service_status()
    print(status)
    if any(value != "ready" for value in status.values()):
        raise SystemExit("Database readiness failed; check local configuration/services")
    with connect() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT VERSION(), VEC_DISTANCE_COSINE("
                       "VEC_FromText('[1,0,0]'), VEC_FromText('[1,0,0]'))")
        version, distance = cursor.fetchone()
        assert abs(distance) < 1e-6, distance
        cursor.execute("SHOW VARIABLES WHERE Variable_name IN (?, ?)", SETTINGS)
        settings = dict(cursor.fetchall())
    print(f"server: {version}")
    for name in SETTINGS:
        print(f"{name} = {settings.get(name)}")
    if not version.startswith(EXPECTED):
        sys.exit(f"FAIL: expected MariaDB {EXPECTED}, got {version}")
    print(f"OK: connected to MariaDB {version}; cosine distance {distance}; both connections OK")


if __name__ == "__main__":
    main()
