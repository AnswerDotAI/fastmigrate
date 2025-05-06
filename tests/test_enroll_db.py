"""Tests for the enroll_db functionality of fastmigrate."""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from fastmigrate.core import enroll_db, get_db_version


def test_enroll_db_on_new_db(tmp_path):
    """Test enrolling a newly created database."""
    # Create a temp file database for testing
    db_path = tmp_path / "test_enroll.db"
    
    # Create empty database file
    conn = sqlite3.connect(db_path)
    conn.close()
    
    # Enroll the database
    result = enroll_db(db_path)
    
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
    
    # Check result is True (table was created)
    assert result is True
    
    # Also verify using get_db_version
    assert get_db_version(db_path) == 0
    
    conn.close()


def test_enroll_db_on_versioned_db(tmp_path):
    """Test enrolling a database that is already versioned."""
    # Create a temp file database for testing
    db_path = tmp_path / "test_enroll.db"
    
    # Create a versioned database
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE _meta (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("INSERT INTO _meta (id, version) VALUES (1, 42)")
    conn.commit()
    conn.close()
    
    # Try to enroll the already versioned database
    result = enroll_db(db_path, err_if_versioned=False)
    
    # Check result is False (table already existed)
    assert result is False
    
    # Verify version wasn't changed
    assert get_db_version(db_path) == 42


def test_enroll_db_on_unversioned_db_with_tables(tmp_path):
    """Test enrolling an existing database with tables but no version tracking."""
    # Create a temp file database for testing
    db_path = tmp_path / "test_enroll.db"    
    
    # Create an unversioned database with a sample table
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO users (name) VALUES ('test_user')")
    conn.commit()
    conn.close()
    
    # Enroll the database
    result = enroll_db(db_path)
    
    # Check result is True (table was created)
    assert result is True
    
    # Verify the version is 0
    assert get_db_version(db_path) == 0
    
    # Verify the sample table still exists
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT name FROM users")
    assert cursor.fetchone()[0] == 'test_user'
    conn.close()


def test_enroll_db_nonexistent_file(tmp_path):
    """Test enrolling a database that doesn't exist."""
    # Create a path to a non-existent database
    db_path = tmp_path / "nonexistent.db"   
    
    # Verify file doesn't exist
    assert not db_path.exists()
    
    # Try to enroll the non-existent database (should raise FileNotFoundError)
    with pytest.raises(FileNotFoundError):
        enroll_db(db_path)


def test_enroll_db_invalid_db(tmp_path):
    """Test enrolling an invalid database file."""
    # Create a temp file with invalid content
    db_path = tmp_path / "bad.db"  
    
    # Write some invalid binary data
    with open(db_path, 'wb') as f:
        f.write(b'This is not a valid SQLite database')
    
    # Try to enroll the invalid database (should raise sqlite3.Error)
    with pytest.raises(sqlite3.Error):
        enroll_db(db_path)