"""Tests for the core functionality of fastmigrate."""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from fastmigrate.core import (
    ensure_meta_table,
    get_db_version,
    set_db_version,
    extract_version_from_filename,
    get_migration_scripts,
    run_migrations,
    create_database_backup,
)


def test_ensure_meta_table():
    """Test ensuring the _meta table exists."""
    # Create a temp file database for testing
    with tempfile.NamedTemporaryFile(suffix='.db') as temp_file:
        db_path = temp_file.name
        
        # Call ensure_meta_table on the path
        ensure_meta_table(db_path)
        
        # Connect and check results
        conn = sqlite3.connect(db_path)
        
        # Check the table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='_meta'")
        assert cursor.fetchone() is not None
        
        # Check there's one row
        cursor = conn.execute("SELECT COUNT(*) FROM _meta")
        assert cursor.fetchone()[0] == 1
        
        # Check the version is 0
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        assert cursor.fetchone()[0] == 0
        
        # Test updating the version
        conn.execute("UPDATE _meta SET version = 42 WHERE id = 1")
        conn.commit()
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        assert cursor.fetchone()[0] == 42
        
        # Verify we can't insert duplicate rows due to constraint
        try:
            conn.execute("INSERT INTO _meta (id, version) VALUES (2, 50)")
            assert False, "Should not be able to insert a row with id != 1"
        except sqlite3.IntegrityError:
            # This is expected - constraint should prevent any id != 1
            pass
        
        conn.close()
    
    # Test with invalid path to verify exception is raised
    with pytest.raises(FileNotFoundError):
        ensure_meta_table("/nonexistent/path/to/db.db")


def test_get_set_db_version():
    """Test getting and setting the database version."""
    # Create a temp file database for testing
    with tempfile.NamedTemporaryFile(suffix='.db') as temp_file:
        db_path = temp_file.name
        
        # Initialize the database first
        ensure_meta_table(db_path)
        
        # Initial version should be 0
        assert get_db_version(db_path) == 0
        
        # Set and get version
        set_db_version(db_path, 42)
        assert get_db_version(db_path) == 42
        
        # Check that id=1 is enforced in the database
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT id FROM _meta")
        assert cursor.fetchone()[0] == 1
        conn.close()
    
    # Test with nonexistent database to verify exceptions
    with pytest.raises(FileNotFoundError):
        get_db_version("/nonexistent/path/to/db.db")
        
    with pytest.raises(FileNotFoundError):
        set_db_version("/nonexistent/path/to/db.db", 50)


def test_extract_version_from_filename():
    """Test extracting version numbers from filenames."""
    # Valid filenames
    assert extract_version_from_filename("0001-create-tables.sql") == 1
    assert extract_version_from_filename("0042-add-column.py") == 42
    assert extract_version_from_filename("9999-final-migration.sh") == 9999
    
    # Invalid filenames
    assert extract_version_from_filename("create-tables.sql") is None
    assert extract_version_from_filename("01-too-short.py") is None
    assert extract_version_from_filename("0001-invalid.txt") is None
    assert extract_version_from_filename("0001_wrong_separator.sql") is None


def test_get_migration_scripts():
    """Test getting migration scripts from a directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test migration files
        Path(temp_dir, "0001-first.sql").touch()
        Path(temp_dir, "0002-second.py").touch()
        Path(temp_dir, "0005-fifth.sh").touch()
        Path(temp_dir, "invalid.txt").touch()
        
        # Get migration scripts
        scripts = get_migration_scripts(temp_dir)
        
        # Check we have the expected scripts
        assert len(scripts) == 3
        assert 1 in scripts
        assert 2 in scripts
        assert 5 in scripts
        assert os.path.basename(scripts[1]) == "0001-first.sql"
        assert os.path.basename(scripts[2]) == "0002-second.py"
        assert os.path.basename(scripts[5]) == "0005-fifth.sh"


def test_get_migration_scripts_duplicate_version():
    """Test that duplicate version numbers are detected."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test migration files with duplicate version
        Path(temp_dir, "0001-first.sql").touch()
        Path(temp_dir, "0001-duplicate.py").touch()
        
        # Get migration scripts - should raise ValueError
        with pytest.raises(ValueError) as excinfo:
            get_migration_scripts(temp_dir)
        
        assert "Duplicate migration version" in str(excinfo.value)


def test_create_database_backup():
    """Test creating a database backup."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a test database
        db_path = os.path.join(temp_dir, "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO test (value) VALUES ('original data')")
        conn.commit()
        conn.close()
        
        # Create a backup
        backup_path = create_database_backup(db_path)
        
        # Check that the backup file exists
        assert os.path.exists(backup_path)
        assert backup_path.startswith(db_path)
        assert ".backup" in backup_path
        
        # Verify the backup contains the same data
        conn_backup = sqlite3.connect(backup_path)
        cursor = conn_backup.execute("SELECT value FROM test")
        assert cursor.fetchone()[0] == "original data"
        conn_backup.close()
        
        # Test backup of non-existent database
        non_existent_path = os.path.join(temp_dir, "nonexistent.db")
        result = create_database_backup(non_existent_path)
        assert result == ""
