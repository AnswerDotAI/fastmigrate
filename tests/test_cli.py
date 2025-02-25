"""Tests for the CLI interface."""

import os
import sqlite3
import tempfile
from pathlib import Path
from typing import List
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from fastmigrate.cli import app


runner = CliRunner()


def test_cli_help():
    """Test the CLI help output."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Run SQLite database migrations" in result.stdout


def test_cli_defaults():
    """Test CLI with default arguments."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Change to temp directory so defaults resolve relative to it
        original_dir = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            # Create migrations directory with a test migration
            os.makedirs("migrations")
            os.makedirs("data")
            
            with open(os.path.join("migrations", "0001-test.sql"), "w") as f:
                f.write("CREATE TABLE test (id INTEGER PRIMARY KEY);")
            
            # Create a config file
            with open(".fastmigrate", "w") as f:
                f.write("[paths]\ndb = data/database.db\nmigrations = migrations")
            
            # Run the CLI
            with patch("sys.argv", ["fastmigrate"]):
                result = runner.invoke(app)
            
            assert result.exit_code == 0
            
            # Verify the database was created and migration applied
            assert os.path.exists("data/database.db")
            conn = sqlite3.connect("data/database.db")
            cursor = conn.execute("SELECT version FROM _meta")
            assert cursor.fetchone()[0] == 1
            
            # Check the migration was applied
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test'")
            assert cursor.fetchone() is not None
            
            conn.close()
        
        finally:
            # Return to original directory
            os.chdir(original_dir)


def test_cli_explicit_paths():
    """Test CLI with explicit path arguments."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create custom directories
        migrations_dir = os.path.join(temp_dir, "custom_migrations")
        db_dir = os.path.join(temp_dir, "custom_data")
        os.makedirs(migrations_dir)
        os.makedirs(db_dir)
        
        db_path = os.path.join(db_dir, "custom.db")
        
        # Create a migration
        with open(os.path.join(migrations_dir, "0001-test.sql"), "w") as f:
            f.write("CREATE TABLE custom (id INTEGER PRIMARY KEY);")
        
        # Run with explicit paths
        result = runner.invoke(app, [
            "--db", db_path,
            "--migrations", migrations_dir
        ])
        
        assert result.exit_code == 0
        
        # Verify the database was created and migration applied
        assert os.path.exists(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version FROM _meta")
        assert cursor.fetchone()[0] == 1
        
        # Check the migration was applied
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='custom'")
        assert cursor.fetchone() is not None
        
        conn.close()


def test_cli_config_file():
    """Test CLI with configuration from file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create custom directories
        migrations_dir = os.path.join(temp_dir, "custom_migrations")
        db_dir = os.path.join(temp_dir, "custom_data")
        os.makedirs(migrations_dir)
        os.makedirs(db_dir)
        
        db_path = os.path.join(db_dir, "custom.db")
        config_path = os.path.join(temp_dir, "custom.ini")
        
        # Create a migration
        with open(os.path.join(migrations_dir, "0001-test.sql"), "w") as f:
            f.write("CREATE TABLE custom_config (id INTEGER PRIMARY KEY);")
        
        # Create a config file
        with open(config_path, "w") as f:
            f.write(f"[paths]\ndb = {db_path}\nmigrations = {migrations_dir}")
        
        # Run with config file
        result = runner.invoke(app, ["--config", config_path])
        
        assert result.exit_code == 0
        
        # Verify the database was created and migration applied
        assert os.path.exists(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version FROM _meta")
        assert cursor.fetchone()[0] == 1
        
        # Check the migration was applied
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='custom_config'"
        )
        assert cursor.fetchone() is not None
        
        conn.close()