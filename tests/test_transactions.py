"""Basic tests for migration functionality."""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from fastmigrate.core import run_migrations, ensure_meta_table


def test_migration_success():
    """Test successful migrations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        db_path = temp_dir_path / "test.db"
        migrations_dir = temp_dir_path / "migrations"
        migrations_dir.mkdir()
        # Create empty database file
        conn = sqlite3.connect(db_path)
        conn.close()
        
        # Initialize the database with _meta table
        ensure_meta_table(str(db_path))
        
        # Create first migration
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
        
        # Create second migration
        with open(migrations_dir / "0002-add-posts.sql", "w") as f:
            f.write("""
            -- Create posts table
            CREATE TABLE posts (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            
            -- Add some sample posts
            INSERT INTO posts (user_id, title) VALUES (1, 'First Post');
            INSERT INTO posts (user_id, title) VALUES (1, 'Second Post');
            """)
        
        # Run migrations
        assert run_migrations(str(db_path), str(migrations_dir)) is True
        
        # Check database state
        conn = sqlite3.connect(db_path)
        
        # Version should be 2
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        assert cursor.fetchone()[0] == 2
        
        # Check users table
        cursor = conn.execute("SELECT username FROM users")
        assert cursor.fetchone()[0] == "admin"
        
        # Check posts table
        cursor = conn.execute("SELECT COUNT(*) FROM posts")
        assert cursor.fetchone()[0] == 2
        
        conn.close()


def test_migration_failure():
    """Test handling of failed migrations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        db_path = temp_dir_path / "test.db"
        migrations_dir = temp_dir_path / "migrations"
        migrations_dir.mkdir()
        # Create empty database file
        conn = sqlite3.connect(db_path)
        conn.close()
        
        # Initialize the database with _meta table
        ensure_meta_table(str(db_path))
        
        # Create first migration
        with open(migrations_dir / "0001-initial.sql", "w") as f:
            f.write("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL
            );
            
            INSERT INTO users (username) VALUES ('admin');
            """)
        
        # Create second migration with syntax error
        with open(migrations_dir / "0002-failing.sql", "w") as f:
            f.write("""
            -- This will fail due to syntax error
            CREATE TABLE posts (id INTEGER PRIMARY KEY,
            -- Missing closing parenthesis
            """)
        
        # Run migrations - should fail on the second migration
        assert run_migrations(str(db_path), str(migrations_dir)) is False
        
        # Check database state
        conn = sqlite3.connect(db_path)
        
        # Version should still be 1
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        assert cursor.fetchone()[0] == 1
        
        # Only first migration should be applied
        cursor = conn.execute("SELECT username FROM users")
        assert cursor.fetchone()[0] == "admin"
        
        conn.close()