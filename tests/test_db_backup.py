"Backup safety against collisions and actual SQLite errors."

from datetime import datetime
from unittest.mock import patch

from fastmigrate.core import create_db, create_db_backup

from test_migrations import query


def test_backup_safety(tmp_path):
    db = tmp_path/'test.db'
    create_db(db)
    query(db, 'CREATE TABLE events (id INTEGER)')
    query(db, 'INSERT INTO events VALUES (1)')
    # Only freeze the clock: backups and collision protection use real SQLite/filesystem operations.
    with patch('fastmigrate.core.datetime') as clock:
        clock.now.return_value = datetime(2026, 1, 1)
        backup = create_db_backup(db)
        query(db, 'INSERT INTO events VALUES (2)')
        assert create_db_backup(db) is None
    assert query(backup, 'SELECT id FROM events') == [(1,)]

    corrupt = tmp_path/'corrupt.db'
    corrupt.write_bytes(b'not a database')
    assert create_db_backup(corrupt) is None
    assert not list(tmp_path.glob('corrupt.db.*.backup'))
