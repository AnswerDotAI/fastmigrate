"""Tests for rollback functionality in migrations."""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from fastmigrate.core import run_migrations, create_db_backup, restore_db_backup


def test_sql_transaction_rollback():
    """Test that SQL migrations are properly rolled back on error.
    
    This test verifies that when an SQL migration fails, all statements
    within that migration are rolled back, preserving the database state
    from the last successful migration.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        db_path = temp_dir_path / "test.db"
        migrations_dir = temp_dir_path / "migrations"
        migrations_dir.mkdir()
        
        # Create first migration - establishes schema
        with open(migrations_dir / "0001-initial.sql", "w") as f:
            f.write("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                email TEXT
            );
            
            -- Insert initial user
            INSERT INTO users (username, email) VALUES ('admin', 'admin@example.com');
            """)
        
        # Create second migration - will fail partway through
        with open(migrations_dir / "0002-failing.sql", "w") as f:
            f.write("""
            -- First statement will succeed
            INSERT INTO users (username, email) VALUES ('user1', 'user1@example.com');
            
            -- This statement creates a new table
            CREATE TABLE posts (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            
            -- This insert will execute
            INSERT INTO posts (user_id, title) VALUES (1, 'First Post');
            
            -- This will fail due to syntax error
            INSERT INTO posts (user_id, title VALUES (2, 'Second Post'); -- Missing closing parenthesis
            
            -- This won't be reached
            INSERT INTO posts (user_id, title) VALUES (1, 'Third Post');
            """)
        
        # Create third migration - only executed if migrations resume correctly
        with open(migrations_dir / "0003-third.sql", "w") as f:
            f.write("""
            INSERT INTO users (username, email) VALUES ('user3', 'user3@example.com');
            """)
        
        # Run migrations - should fail on the second migration
        assert run_migrations(str(db_path), str(migrations_dir)) is False
        
        # Check database state
        conn = sqlite3.connect(db_path)
        
        # Version should be 1 (only first migration succeeded)
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        assert cursor.fetchone()[0] == 1
        
        # Verify the users table exists with only the admin user from migration 1
        cursor = conn.execute("SELECT COUNT(*) FROM users")
        assert cursor.fetchone()[0] == 1
        
        cursor = conn.execute("SELECT username FROM users")
        assert cursor.fetchone()[0] == "admin"
        
        # The posts table should not exist since migration 2 failed and was rolled back
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='posts'"
        )
        assert cursor.fetchone() is None
        
        # Fix the second migration
        with open(migrations_dir / "0002-fixed.sql", "w") as f:
            f.write("""
            -- First statement will succeed
            INSERT INTO users (username, email) VALUES ('user1', 'user1@example.com');
            
            -- This statement creates a new table
            CREATE TABLE posts (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            
            -- These will execute successfully
            INSERT INTO posts (user_id, title) VALUES (1, 'First Post');
            INSERT INTO posts (user_id, title) VALUES (1, 'Third Post');
            """)
        
        # Remove the failing migration
        (migrations_dir / "0002-failing.sql").unlink()
        
        # Run migrations again - should execute 0002-fixed.sql and 0003-third.sql
        assert run_migrations(str(db_path), str(migrations_dir)) is True
        
        # Check database state after successful migrations
        # Version should be 3
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        assert cursor.fetchone()[0] == 3
        
        # Should have all users from all three migrations
        cursor = conn.execute("SELECT username FROM users ORDER BY id")
        usernames = [row[0] for row in cursor.fetchall()]
        assert usernames == ["admin", "user1", "user3"]
        
        # Posts table should exist with two entries
        cursor = conn.execute("SELECT COUNT(*) FROM posts")
        assert cursor.fetchone()[0] == 2
        
        conn.close()


def test_large_transaction_rollback():
    """Test rollback of a large migration with many statements."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        db_path = temp_dir_path / "test.db"
        migrations_dir = temp_dir_path / "migrations"
        migrations_dir.mkdir()
        
        # Create initial migration
        with open(migrations_dir / "0001-initial.sql", "w") as f:
            f.write("""
            CREATE TABLE data (
                id INTEGER PRIMARY KEY,
                value TEXT NOT NULL
            );
            """)
        
        # Create a large migration with many inserts and a failure at the end
        with open(migrations_dir / "0002-large.sql", "w") as f:
            # Write 100 valid INSERT statements
            for i in range(1, 101):
                f.write(f"INSERT INTO data (id, value) VALUES ({i}, 'value-{i}');\n")
            
            # Add a statement that will fail
            f.write("CREATE TABLE will_fail (id INTEGER PRIMARY KEY,\n")  # Incomplete statement
        
        # Run migrations - should fail on the second migration
        assert run_migrations(str(db_path), str(migrations_dir)) is False
        
        # Check database state
        conn = sqlite3.connect(db_path)
        
        # Version should be 1 (only first migration succeeded)
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        assert cursor.fetchone()[0] == 1
        
        # The data table should exist but be empty
        cursor = conn.execute("SELECT COUNT(*) FROM data")
        assert cursor.fetchone()[0] == 0
        
        conn.close()


def test_backup_restore_functionality():
    """Test the backup and restore functionality directly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        db_path = str(temp_dir_path / "test.db")
        
        # Create a test database with some data
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO test (name) VALUES ('original')")
        conn.commit()
        conn.close()
        
        # Create a backup
        backup_path = create_db_backup(db_path)
        assert os.path.exists(backup_path)
        
        # Modify the original database
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO test (name) VALUES ('modified')")
        conn.commit()
        conn.close()
        
        # Verify the modification
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM test")
        assert cursor.fetchone()[0] == 2
        conn.close()
        
        # Restore from backup
        assert restore_db_backup(backup_path, db_path)
        
        # Verify the database was restored to its original state
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM test")
        assert cursor.fetchone()[0] == 1
        cursor = conn.execute("SELECT name FROM test")
        assert cursor.fetchone()[0] == "original"
        conn.close()
        
        # Backup file should be removed after restore
        assert not os.path.exists(backup_path)


def test_python_script_rollback():
    """Test rollback when a Python migration script fails."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        db_path = temp_dir_path / "test.db"
        migrations_dir = temp_dir_path / "migrations"
        migrations_dir.mkdir()
        
        # Create initial migration to set up the schema
        with open(migrations_dir / "0001-initial.sql", "w") as f:
            f.write("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL
            );
            
            INSERT INTO users (username) VALUES ('admin');
            """)
        
        # Create a Python migration that will fail
        with open(migrations_dir / "0002-python.py", "w") as f:
            f.write("""
import sqlite3
import sys

def main(db_path):
    conn = sqlite3.connect(db_path)
    try:
        # This will succeed
        conn.execute("INSERT INTO users (username) VALUES ('user1')")
        conn.commit()
        
        # This will fail - users table doesn't have an email column
        conn.execute("INSERT INTO users (username, email) VALUES ('user2', 'user2@example.com')")
        conn.commit()
    finally:
        conn.close()
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
            """)
        
        # Run migrations - should fail on the Python script
        assert run_migrations(str(db_path), str(migrations_dir)) is False
        
        # Check database state
        conn = sqlite3.connect(db_path)
        
        # Version should be 1
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        assert cursor.fetchone()[0] == 1
        
        # Only the admin user should exist (not user1), verifying rollback worked
        cursor = conn.execute("SELECT COUNT(*) FROM users")
        assert cursor.fetchone()[0] == 1
        
        cursor = conn.execute("SELECT username FROM users")
        assert cursor.fetchone()[0] == "admin"
        
        conn.close()


def test_shell_script_rollback():
    """Test rollback when a shell script migration fails."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        db_path = temp_dir_path / "test.db"
        migrations_dir = temp_dir_path / "migrations"
        migrations_dir.mkdir()
        
        # Create initial migration to set up the schema
        with open(migrations_dir / "0001-initial.sql", "w") as f:
            f.write("""
            CREATE TABLE notes (
                id INTEGER PRIMARY KEY,
                content TEXT NOT NULL
            );
            
            INSERT INTO notes (content) VALUES ('Initial note');
            """)
        
        # Create a shell script that will fail
        with open(migrations_dir / "0002-shell.sh", "w") as f:
            f.write("""#!/bin/sh
DB_PATH="$1"

# This command will succeed
sqlite3 "$DB_PATH" "INSERT INTO notes (content) VALUES ('Note from shell script')"

# This command will fail - intentional syntax error
sqlite3 "$DB_PATH" "INSERT INTO notes (content VALUES ('This will fail')"

# Exit with error
exit 1
            """)
        os.chmod(migrations_dir / "0002-shell.sh", 0o755)  # Make executable
        
        # Run migrations - should fail on the shell script
        assert run_migrations(str(db_path), str(migrations_dir)) is False
        
        # Check database state
        conn = sqlite3.connect(db_path)
        
        # Version should be 1
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        assert cursor.fetchone()[0] == 1
        
        # Only the initial note should exist, verifying rollback worked
        cursor = conn.execute("SELECT COUNT(*) FROM notes")
        assert cursor.fetchone()[0] == 1
        
        cursor = conn.execute("SELECT content FROM notes")
        assert cursor.fetchone()[0] == "Initial note"
        
        conn.close()