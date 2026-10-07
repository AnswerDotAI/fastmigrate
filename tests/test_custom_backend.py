"Real adapter integrations for synchronous and asynchronous migration entry points."

import asyncio

import pytest

from fastmigrate.core import arun_migrations, run_migrations

from test_migrations import query, write_migrations


def test_sqlalchemy_backend(tmp_path):
    pytest.importorskip('sqlalchemy')
    db, migrations = tmp_path/'test.db', tmp_path/'migrations'
    write_migrations(migrations, {
        'config.py': '''from sqlalchemy import create_engine

def get_connection(db): return create_engine(f'sqlite+pysqlite:///{db}')
def close_connection(engine): engine.dispose()

def ensure_meta_table(engine):
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE IF NOT EXISTS _meta (id INTEGER PRIMARY KEY, version INTEGER)')
        conn.exec_driver_sql('INSERT OR IGNORE INTO _meta VALUES (1, 0)')

def get_version(engine):
    with engine.connect() as conn: return conn.exec_driver_sql('SELECT version FROM _meta WHERE id=1').scalar_one()

def set_version(engine, version):
    with engine.begin() as conn: conn.exec_driver_sql('UPDATE _meta SET version=? WHERE id=1', (version,))

def execute_sql(engine, sql):
    with engine.begin() as conn:
        for stmt in sql.split(';'):
            if stmt.strip(): conn.exec_driver_sql(stmt)
''',
        '0001-create.sql': 'CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);',
        '0002-insert.sql': "INSERT INTO users VALUES (1, 'alice');",
        '0003-insert.py': '''import sqlite3, sys
with sqlite3.connect(sys.argv[1]) as conn: conn.execute("INSERT INTO users VALUES (2, 'bob')")
''',
    })
    assert run_migrations(db, migrations)
    assert query(db, 'SELECT version FROM _meta') == [(3,)]
    assert query(db, 'SELECT id, name FROM users ORDER BY id') == [(1, 'alice'), (2, 'bob')]


def test_duckdb_async_backend(tmp_path):
    duckdb = pytest.importorskip('duckdb')
    db, migrations = tmp_path/'test.duckdb', tmp_path/'migrations'
    write_migrations(migrations, {
        'config.py': '''import asyncio, duckdb

_loop = None

def check_loop():
    global _loop
    current = asyncio.get_running_loop()
    if _loop is None: _loop = current
    assert current is _loop, 'Hooks executed on different event loops'

async def get_connection(db):
    check_loop()
    return duckdb.connect(str(db))

async def close_connection(conn):
    check_loop()
    conn.close()

async def ensure_meta_table(conn):
    check_loop()
    conn.execute('CREATE TABLE IF NOT EXISTS _meta (id INTEGER PRIMARY KEY, version INTEGER)')
    conn.execute('INSERT INTO _meta SELECT 1, 0 WHERE NOT EXISTS (SELECT 1 FROM _meta)')

async def get_version(conn):
    check_loop()
    return conn.execute('SELECT version FROM _meta WHERE id=1').fetchone()[0]

async def set_version(conn, version):
    check_loop()
    conn.execute('UPDATE _meta SET version=? WHERE id=1', [version])

async def execute_sql(conn, sql):
    check_loop()
    conn.execute(sql)
''',
        '0001-create.sql': 'CREATE TABLE things (id INTEGER, name TEXT);',
        '0002-insert.sql': "INSERT INTO things VALUES (1, 'hello');",
    })
    assert asyncio.run(arun_migrations(db, migrations))
    with duckdb.connect(str(db)) as conn:
        assert conn.execute('SELECT version FROM _meta').fetchall() == [(2,)]
        assert conn.execute('SELECT id, name FROM things').fetchall() == [(1, 'hello')]
    # The sync entry point must also execute pending async hooks, not merely an up-to-date check.
    (migrations/'0003-insert.sql').write_text("INSERT INTO things VALUES (2, 'world');")
    assert run_migrations(db, migrations)
    with duckdb.connect(str(db)) as conn:
        assert conn.execute('SELECT version FROM _meta').fetchall() == [(3,)]
        assert conn.execute('SELECT id, name FROM things ORDER BY id').fetchall() == [(1, 'hello'), (2, 'world')]
