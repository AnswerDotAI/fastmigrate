import pytest
import sqlite3
import os
import tempfile
from datetime import datetime
from pathlib import Path

from fastmigrate.core import create_db_backup

# this test used pytest-mock which automatically cleans up the mock patches during test teardown
# https://pytest-mock.readthedocs.io/en/latest/


@pytest.fixture
def temp_db():
    """Provides a temporary directory and a path to a test database."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO test (value) VALUES ('original data')")
        conn.commit()
        conn.close()
        yield db_path, temp_dir  # Yield both db_path and temp_dir


def test_create_db_backup_success(temp_db):
    """Test successful creation of a database backup."""
    db_path, _ = temp_db  # Unpack the fixture result

    backup_path = create_db_backup(db_path)

    assert backup_path is not None
    assert os.path.exists(backup_path)
    assert str(backup_path).startswith(db_path)
    assert ".backup" in os.path.basename(backup_path)  # Check basename for .backup

    # Verify the backup contains the same data
    conn_backup = sqlite3.connect(backup_path)
    cursor = conn_backup.execute("SELECT value FROM test")
    assert cursor.fetchone()[0] == "original data"
    conn_backup.close()


def test_create_db_backup_db_not_exists(temp_db):
    """Test backup attempt when the source database does not exist."""
    _, temp_dir = temp_db  # We only need the directory from the fixture
    non_existent_path = os.path.join(temp_dir, "nonexistent.db")

    result = create_db_backup(non_existent_path)

    assert result is None


def test_create_db_backup_already_exists(temp_db, mocker):
    """Test backup attempt when the target backup file already exists."""
    db_path, _ = temp_db

    fixed_timestamp = "20230101_120000"
    expected_backup_path = f"{db_path}.{fixed_timestamp}.backup"

    # Create the dummy existing backup file
    with open(expected_backup_path, "w") as f:
        f.write("dummy content")

    # Mock datetime using pytest-mock
    mock_dt = mocker.patch("fastmigrate.core.datetime")
    mock_dt.now.return_value = datetime.strptime(fixed_timestamp, "%Y%m%d_%H%M%S")
    mock_dt.strptime = datetime.strptime

    result = create_db_backup(db_path)

    assert result is None
    assert os.path.exists(expected_backup_path)  # Ensure the original dummy file wasn't removed


def test_create_db_backup_removes_file_on_error(temp_db, mocker):
    """Test that if an error occurs after backup, the backup file is removed."""
    import sqlite3

    db_path, _ = temp_db

    # Mock datetime and predict path
    fixed_timestamp = "20230101_000000"
    mock_dt = mocker.patch("fastmigrate.core.datetime")
    mock_dt.now.return_value = datetime.strptime(fixed_timestamp, "%Y%m%d_%H%M%S")
    mock_dt.strptime = datetime.strptime
    predicted_backup_path = f"{db_path}.{fixed_timestamp}.backup"

    # Patch connect: source is mocked, backup is real
    real_connect = sqlite3.connect

    def mock_connect(db_file_path):
        if Path(db_file_path) == Path(db_path):
            # Return the mock source connection
            return mock_conn
        # Allow real connection for the backup file
        return real_connect(db_file_path)

    # Define backup method: do real backup, then raise error
    def backup_and_fail(target_conn, *args, **kwargs):
        # Actually create the backup file
        real_conn = real_connect(db_path)
        try:
            real_conn.backup(target_conn)
        finally:
            real_conn.close()
        # Now simulate error during the backup
        raise Exception("Simulated error during the backup")

    mock_conn = mocker.MagicMock()
    mock_conn.backup.side_effect = backup_and_fail

    mocker.patch("fastmigrate.core.sqlite3.connect", side_effect=mock_connect)

    result = create_db_backup(db_path)

    assert result is None
    # Ensure backup was actually called
    mock_conn.backup.assert_called_once()
    # Assert that the backup file does not exist after the failed operation
    assert not os.path.exists(predicted_backup_path)
