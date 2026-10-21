"""Transactional Postgres backend with SQLite-compatible rows and query placeholders.

The same deterministic Relay application logic runs on SQLite in local tests
and managed Postgres for persistent hosted pairing/OAuth/job state.
Never silently fall back from Postgres to ephemeral SQLite on a host.
"""
from contextlib import contextmanager
import psycopg


class CompatibleRow(dict):
    """Support both sqlite3.Row['column'] and sqlite3.Row[index]."""

    def __getitem__(self, key):
        if type(key) is int:
            return list(self.values())[key]
        return super().__getitem__(key)


def rows(cursor):
    columns = [column.name for column in cursor.description]
    return lambda values: CompatibleRow(zip(columns, values))


class Database:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, params=()):
        # The sqlite version uses a positional rowid. PostgreSQL has a
        # monotonically assigned BIGSERIAL for immutable FIFO ordering.
        if statement.startswith("INSERT OR REPLACE INTO rates VALUES"):
            statement = ("INSERT INTO rates(key,bucket,count) VALUES (%s,%s,%s) "
                         "ON CONFLICT (key) DO UPDATE SET bucket=EXCLUDED.bucket, count=EXCLUDED.count")
        else:
            statement = statement.replace("?", "%s")
        return self.connection.execute(statement, params)

    def executescript(self, script):
        script = script.replace(
            "CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,request TEXT,device TEXT,digest TEXT,",
            "CREATE TABLE IF NOT EXISTS jobs(rowid BIGSERIAL UNIQUE,id TEXT PRIMARY KEY,request TEXT,device TEXT,digest TEXT,",
        )
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement.strip())


@contextmanager
def pg_session(dsn):
    # Serialize durable queue and token state atomically across possible
    # free-service reconnects. The relay is intentionally single-workspace.
    with psycopg.connect(dsn, row_factory=rows, connect_timeout=10) as connection:
        with connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock(125349873)")
            yield Database(connection)
