"""Host-side database connections; never imported by browser code."""
import os
from contextlib import contextmanager

import mariadb
from dotenv import load_dotenv
from neo4j import GraphDatabase


def configure():
    load_dotenv()


@contextmanager
def connect(database=None):
    """Yield a MariaDB connection from .env. autocommit is off: call commit() yourself."""
    configure()
    connection = mariadb.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "citehop"),
        password=os.environ["DB_PASS"],
        database=database or os.getenv("DB_NAME", "citehop"),
        autocommit=False, connect_timeout=3, read_timeout=5, write_timeout=5,
    )
    try:
        yield connection
    finally:
        connection.close()


def graph_driver():
    configure()
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
        connection_timeout=3, connection_acquisition_timeout=5,
        max_transaction_retry_time=0,
    )
