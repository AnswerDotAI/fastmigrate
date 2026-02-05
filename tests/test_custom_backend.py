"""Tests for the db-independent backend adapter (migrations/config.py).

These tests are written to run when optional dev dependencies are installed.
If SQLAlchemy / DuckDB are missing, the tests are skipped.
"""

from __future__ import annotations

import textwrap
import sqlite3
from pathlib import Path

import pytest

from fastmigrate.core import run_migrations


def test_custom_config_with_sqlalchemy_sqlite(tmp_path: Path) -> None:
    sqlalchemy = pytest.importorskip("sqlalchemy")

    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()

    db_path = tmp_path / "test.db"

    # A simple SQLAlchemy-based adapter. It uses a SQLAlchemy Engine as the
    # "connection object" passed around by fastmigrate.
    (migrations_dir / "config.py").write_text(
        textwrap.dedent(
            """
            from sqlalchemy import create_engine

            def get_connection(db):
                return create_engine(f"sqlite+pysqlite:///{db}")

            def close_connection(engine):
                engine.dispose()

            def ensure_meta_table(engine):
                with engine.begin() as conn:
                    conn.exec_driver_sql(
                        "CREATE TABLE IF NOT EXISTS _meta (id INTEGER PRIMARY KEY, version INTEGER NOT NULL)"
                    )
                    row = conn.exec_driver_sql("SELECT version FROM _meta WHERE id=1").fetchone()
                    if row is None:
                        conn.exec_driver_sql("INSERT INTO _meta (id, version) VALUES (1, 0)")

            def get_version(engine) -> int:
                with engine.connect() as conn:
                    row = conn.exec_driver_sql("SELECT version FROM _meta WHERE id=1").fetchone()
                    return int(row[0]) if row else 0

            def set_version(engine, version: int):
                with engine.begin() as conn:
                    conn.exec_driver_sql("DELETE FROM _meta WHERE id=1")
                    conn.exec_driver_sql(
                        "INSERT INTO _meta (id, version) VALUES (1, ?)",
                        (int(version),),
                    )

            def execute_sql(engine, sql: str):
                # Basic split; good enough for the test suite.
                stmts = [s.strip() for s in sql.split(';') if s.strip()]
                with engine.begin() as conn:
                    for stmt in stmts:
                        conn.exec_driver_sql(stmt)
            """
        )
    )

    # Add migrations. We include a .py migration to ensure those still work in
    # custom-backend mode.
    (migrations_dir / "0001-create-users.sql").write_text(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);"
    )
    (migrations_dir / "0002-insert-user.sql").write_text(
        "INSERT INTO users (id, name) VALUES (1, 'alice');"
    )

    (migrations_dir / "0003-insert-user.py").write_text(
        textwrap.dedent(
            """
            import sqlite3
            import sys

            db_path = sys.argv[1]
            conn = sqlite3.connect(db_path)
            conn.execute("INSERT INTO users (id, name) VALUES (?, ?)", (2, "bob"))
            conn.commit()
            conn.close()
            """
        )
    )

    assert run_migrations(db_path, migrations_dir, verbose=True) is True

    # Verify database state using sqlite3 directly.
    conn = sqlite3.connect(db_path)
    try:
        # Version should be 3
        row = conn.execute("SELECT version FROM _meta WHERE id=1").fetchone()
        assert row is not None
        assert row[0] == 3

        users = conn.execute("SELECT id, name FROM users ORDER BY id").fetchall()
        assert users == [(1, "alice"), (2, "bob")]
    finally:
        conn.close()


def test_custom_config_with_duckdb_async(tmp_path: Path) -> None:
    duckdb = pytest.importorskip("duckdb")

    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()

    db_path = tmp_path / "test.duckdb"

    # An adapter that uses async hooks (even though duckdb itself is sync) to
    # verify fastmigrate correctly awaits coroutines and keeps everything on the
    # same event loop.
    (migrations_dir / "config.py").write_text(
        textwrap.dedent(
            """
            import asyncio
            import duckdb

            _LOOP = None

            def _assert_same_loop():
                global _LOOP
                loop = asyncio.get_running_loop()
                if _LOOP is None:
                    _LOOP = loop
                else:
                    assert loop is _LOOP, "Hooks executed on different event loops"

            async def get_connection(db):
                _assert_same_loop()
                return duckdb.connect(str(db))

            async def close_connection(conn):
                _assert_same_loop()
                conn.close()

            async def ensure_meta_table(conn):
                _assert_same_loop()
                conn.execute("CREATE TABLE IF NOT EXISTS _meta (id INTEGER, version INTEGER)")
                row = conn.execute("SELECT version FROM _meta WHERE id=1").fetchone()
                if row is None:
                    conn.execute("INSERT INTO _meta VALUES (1, 0)")

            async def get_version(conn) -> int:
                _assert_same_loop()
                row = conn.execute("SELECT version FROM _meta WHERE id=1").fetchone()
                return int(row[0]) if row else 0

            async def set_version(conn, version: int):
                _assert_same_loop()
                conn.execute("DELETE FROM _meta WHERE id=1")
                conn.execute("INSERT INTO _meta VALUES (1, ?)", [int(version)])

            async def execute_sql(conn, sql: str):
                _assert_same_loop()
                # Basic split; good enough for the test suite.
                for stmt in [s.strip() for s in sql.split(';') if s.strip()]:
                    conn.execute(stmt)
            """
        )
    )

    (migrations_dir / "0001-create-things.sql").write_text(
        "CREATE TABLE things (id INTEGER, name TEXT);"
    )
    (migrations_dir / "0002-insert-thing.sql").write_text(
        "INSERT INTO things VALUES (1, 'hello');"
    )

    assert run_migrations(db_path, migrations_dir, verbose=True) is True

    conn = duckdb.connect(str(db_path))
    try:
        row = conn.execute("SELECT version FROM _meta WHERE id=1").fetchone()
        assert row is not None
        assert row[0] == 2

        things = conn.execute("SELECT id, name FROM things ORDER BY id").fetchall()
        assert things == [(1, "hello")]
    finally:
        conn.close()
