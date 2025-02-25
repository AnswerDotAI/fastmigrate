"""Integration tests for fastmigrate."""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from fastmigrate.core import run_migrations


def test_run_migrations_sql():
    """Test running SQL migrations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create migrations directory
        migrations_dir = os.path.join(temp_dir, "migrations")
        os.makedirs(migrations_dir)
        
        # Create a test database
        db_path = os.path.join(temp_dir, "test.db")
        
        # Create SQL migration files
        with open(os.path.join(migrations_dir, "0001-create-table.sql"), "w") as f:
            f.write("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );
            """)
        
        with open(os.path.join(migrations_dir, "0002-add-data.sql"), "w") as f:
            f.write("""
            INSERT INTO users (name) VALUES ('Alice');
            INSERT INTO users (name) VALUES ('Bob');
            """)
        
        # Run migrations
        assert run_migrations(db_path, migrations_dir) is True
        
        # Check the database changes
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version FROM _meta")
        assert cursor.fetchone()[0] == 2  # Version should be updated to the last migration
        
        cursor = conn.execute("SELECT COUNT(*) FROM users")
        assert cursor.fetchone()[0] == 2  # Should have 2 users
        
        cursor = conn.execute("SELECT name FROM users ORDER BY id")
        names = [row[0] for row in cursor.fetchall()]
        assert names == ["Alice", "Bob"]
        
        # Add another migration
        with open(os.path.join(migrations_dir, "0003-add-column.sql"), "w") as f:
            f.write("""
            ALTER TABLE users ADD COLUMN email TEXT;
            UPDATE users SET email = 'alice@example.com' WHERE name = 'Alice';
            UPDATE users SET email = 'bob@example.com' WHERE name = 'Bob';
            """)
        
        # Run migrations again
        assert run_migrations(db_path, migrations_dir) is True
        
        # Check the version is updated
        cursor = conn.execute("SELECT version FROM _meta")
        assert cursor.fetchone()[0] == 3
        
        # Check the new column
        cursor = conn.execute("SELECT name, email FROM users ORDER BY id")
        results = cursor.fetchall()
        assert results == [("Alice", "alice@example.com"), ("Bob", "bob@example.com")]
        
        conn.close()


def test_run_migrations_python():
    """Test running Python migrations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create migrations directory
        migrations_dir = os.path.join(temp_dir, "migrations")
        os.makedirs(migrations_dir)
        
        # Create a test database
        db_path = os.path.join(temp_dir, "test.db")
        
        # Create a base SQL migration
        with open(os.path.join(migrations_dir, "0001-create-table.sql"), "w") as f:
            f.write("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );
            """)
        
        # Create Python migration
        with open(os.path.join(migrations_dir, "0002-add-data.py"), "w") as f:
            f.write("""#!/usr/bin/env python
import sqlite3
import sys

def main():
    db_path = sys.argv[1]
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO users (name) VALUES ('Charlie')")
    conn.execute("INSERT INTO users (name) VALUES ('Dave')")
    conn.commit()
    conn.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
            """)
        
        # Run migrations
        assert run_migrations(db_path, migrations_dir) is True
        
        # Check the database changes
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version FROM _meta")
        assert cursor.fetchone()[0] == 2
        
        cursor = conn.execute("SELECT name FROM users ORDER BY id")
        names = [row[0] for row in cursor.fetchall()]
        assert names == ["Charlie", "Dave"]
        
        conn.close()


def test_run_migrations_failed():
    """Test handling of failed migrations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create migrations directory
        migrations_dir = os.path.join(temp_dir, "migrations")
        os.makedirs(migrations_dir)
        
        # Create a test database
        db_path = os.path.join(temp_dir, "test.db")
        
        # Create a valid migration
        with open(os.path.join(migrations_dir, "0001-create-table.sql"), "w") as f:
            f.write("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );
            """)
        
        # Create an invalid migration (syntax error)
        with open(os.path.join(migrations_dir, "0002-invalid.sql"), "w") as f:
            f.write("""
            INSERT INTO users (name VALUES ('Alice');  -- Missing closing parenthesis
            """)
        
        # Run migrations - should fail
        assert run_migrations(db_path, migrations_dir) is False
        
        # Check the database version is still 1
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version FROM _meta")
        assert cursor.fetchone()[0] == 1
        
        conn.close()