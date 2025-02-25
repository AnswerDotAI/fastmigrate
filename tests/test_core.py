"""Tests for the core functionality of fastmigrate."""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from fastmigrate.core import (
    ensure_meta_table,
    get_db_version,
    set_db_version,
    extract_version_from_filename,
    get_migration_scripts,
)


def test_ensure_meta_table():
    """Test ensuring the _meta table exists."""
    # Create an in-memory database
    conn = sqlite3.connect(":memory:")
    ensure_meta_table(conn)
    
    # Check the table exists
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='_meta'")
    assert cursor.fetchone() is not None
    
    # Check there's one row
    cursor = conn.execute("SELECT COUNT(*) FROM _meta")
    assert cursor.fetchone()[0] == 1
    
    # Check the version is 0
    cursor = conn.execute("SELECT version FROM _meta")
    assert cursor.fetchone()[0] == 0
    
    # Test with existing data
    conn.execute("DELETE FROM _meta")
    conn.execute("INSERT INTO _meta (version) VALUES (42)")
    conn.execute("INSERT INTO _meta (version) VALUES (43)")
    ensure_meta_table(conn)
    
    # Should be reset to a single row with version 0
    cursor = conn.execute("SELECT COUNT(*) FROM _meta")
    assert cursor.fetchone()[0] == 1
    cursor = conn.execute("SELECT version FROM _meta")
    assert cursor.fetchone()[0] == 0


def test_get_set_db_version():
    """Test getting and setting the database version."""
    conn = sqlite3.connect(":memory:")
    ensure_meta_table(conn)
    
    # Initial version should be 0
    assert get_db_version(conn) == 0
    
    # Set and get version
    set_db_version(conn, 42)
    assert get_db_version(conn) == 42


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