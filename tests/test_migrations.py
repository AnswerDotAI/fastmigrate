"Real migration journeys, from database enrollment through failure and recovery."

import shlex, sqlite3, subprocess, sys
from contextlib import closing

import pytest

from fastmigrate.core import create_db, get_db_version, get_migration_scripts, run_migrations


def query(db, sql):
    with closing(sqlite3.connect(db)) as conn, conn: return conn.execute(sql).fetchall()


def write_migrations(directory, files):
    directory.mkdir(exist_ok=True)
    for name, content in files.items(): (directory/name).write_text(content)


def cli(command, *args):
    return subprocess.run([f'fastmigrate_{command}', *map(str, args)], capture_output=True, text=True, timeout=30)


@pytest.fixture
def migration_project(tmp_path):
    db, migrations = tmp_path/'test.db', tmp_path/'migrations'
    create_db(db)
    migrations.mkdir()
    return db, migrations


def test_migration_journey(migration_project):
    db, migrations = migration_project
    with pytest.raises(sqlite3.IntegrityError): query(db, 'INSERT INTO _meta VALUES (2, 99)')

    # Create scripts out of order. Non-idempotent inserts expose repeats and wrong ordering.
    write_migrations(migrations, {
        '0010-shell.sh': f'''{shlex.quote(sys.executable)} - "$1" <<'PY'
import sqlite3, sys
with sqlite3.connect(sys.argv[1]) as conn: conn.execute('INSERT INTO events (version) VALUES (10)')
PY
''',
        '0001-create.sql': 'CREATE TABLE events (id INTEGER PRIMARY KEY, version INTEGER, note TEXT); INSERT INTO events (version) VALUES (1);',
        '0003-python.py': '''import sqlite3, sys
with sqlite3.connect(sys.argv[1]) as conn: conn.execute('INSERT INTO events (version) VALUES (3)')
''',
        '0002-ignored.txt': 'not a migration',
    })
    result = cli('run_migrations', '--db', db, '--migrations', migrations)
    assert result.returncode == 0, result.stderr
    assert get_db_version(db) == 10
    assert query(db, 'SELECT version FROM events ORDER BY id') == [(1,), (3,), (10,)]
    assert run_migrations(db, migrations)
    assert query(db, 'SELECT version FROM events ORDER BY id') == [(1,), (3,), (10,)]

    # A failed SQL migration may leave changes, but must not advance the version or run later scripts.
    write_migrations(migrations, {
        '0005-old.sql': 'this would fail if an already-passed version were executed',
        '0015-failing.sql': 'INSERT INTO events (version) VALUES (15); INSERT INTO missing VALUES (1);',
        '0020-later.sql': 'INSERT INTO events (version) VALUES (20);',
    })
    assert not run_migrations(db, migrations)
    assert get_db_version(db) == 10
    assert query(db, 'SELECT version FROM events ORDER BY id') == [(1,), (3,), (10,), (15,)]
    (migrations/'0015-failing.sql').write_text("UPDATE events SET note='recovered' WHERE version=15;")
    assert run_migrations(db, migrations)
    assert create_db(db) == 20
    assert query(db, 'SELECT version FROM events ORDER BY id') == [(1,), (3,), (10,), (15,), (20,)]
    assert query(db, 'SELECT note FROM events WHERE version=15') == [('recovered',)]


@pytest.mark.parametrize('extension, failure', [('py', 'import sys; sys.exit(7)'), ('sh', 'exit 7')])
def test_external_script_failure(migration_project, extension, failure):
    db, migrations = migration_project
    write_migrations(migrations, {
        '0001-create.sql': 'CREATE TABLE events (id INTEGER); INSERT INTO events VALUES (1);',
        f'0002-fail.{extension}': failure,
        '0003-later.sql': 'INSERT INTO events VALUES (3);',
    })
    assert cli('run_migrations', '--db', db, '--migrations', migrations).returncode != 0
    assert get_db_version(db) == 1
    assert query(db, 'SELECT id FROM events') == [(1,)]


def test_enrollment_backup_and_config_precedence(tmp_path):
    db, migrations, config = tmp_path/'existing.db', tmp_path/'migrations', tmp_path/'config.ini'
    query(db, 'CREATE TABLE events (value TEXT)')
    query(db, "INSERT INTO events VALUES ('original')")
    write_migrations(migrations, {'0002-update.sql': "UPDATE events SET value='updated';"})
    with pytest.raises(sqlite3.Error): create_db(db)
    assert not run_migrations(db, migrations)
    assert query(db, 'SELECT value FROM events') == [('original',)]
    assert query(db, "SELECT name FROM sqlite_master WHERE name='_meta'") == []

    config.write_text(f'[paths]\ndb={db}\nmigrations={migrations}\n')
    result = cli('enroll_db', '--config_path', config)
    assert result.returncode == 0, result.stderr
    assert get_db_version(db) == 1
    assert query(db, 'SELECT value FROM events') == [('original',)]
    other_db, other_migrations = tmp_path/'other.db', tmp_path/'other_migrations'
    create_db(other_db)
    query(other_db, (migrations/'0001-initialize.sql').read_text())
    assert cli('backup_db', '--config_path', config).returncode == 0
    backup, = tmp_path.glob('existing.db.*.backup')

    # Explicit CLI paths must win over a config pointing at a different database and migration directory.
    write_migrations(other_migrations, {'0009-wrong.sql': 'invalid SQL'})
    config.write_text(f'[paths]\ndb={other_db}\nmigrations={other_migrations}\n')
    result = cli('run_migrations', '--config_path', config, '--db', db, '--migrations', migrations)
    assert result.returncode == 0, result.stderr
    assert get_db_version(db) == 2
    assert get_db_version(other_db) == 0
    assert query(db, 'SELECT value FROM events') == [('updated',)]
    assert get_db_version(backup) == 1
    assert query(backup, 'SELECT value FROM events') == [('original',)]
    assert cli('enroll_db', '--db', db, '--migrations', migrations).returncode != 0
    assert get_db_version(db) == 2


def test_duplicate_versions_rejected(migration_project):
    _, migrations = migration_project
    write_migrations(migrations, {'0001-first.sql': '', '0001-second.py': ''})
    with pytest.raises(ValueError, match='Duplicate migration version'): get_migration_scripts(migrations)
