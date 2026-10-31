"""Real connection and tiny native-vector check (no persistent writes)."""
from citehop.db import connect
from citehop.health import service_status


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
        print(f"MariaDB {version}: cosine distance {distance}; both connections OK")


if __name__ == "__main__":
    main()
