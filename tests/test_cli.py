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

# Path to the test suite
TESTSUITE_A_DIR = Path(__file__).parent.parent / "testsuites" / "testsuite_a"


def test_cli_help():
    """Test the CLI help output."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Run SQLite database migrations" in result.stdout


def test_cli_defaults():
    """Test CLI with default arguments."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Change to temp directory so defaults resolve relative to it
        original_dir = Path.cwd()
        temp_dir_path = Path(temp_dir)
        os.chdir(temp_dir_path)
        
        try:
            # Create migrations directory with a test migration
            migrations_path = temp_dir_path / "migrations"
            data_path = temp_dir_path / "data"
            migrations_path.mkdir()
            data_path.mkdir()
            
            with open(migrations_path / "0001-test.sql", "w") as f:
                f.write("CREATE TABLE test (id INTEGER PRIMARY KEY);")
            
            # Create a config file
            with open(temp_dir_path / ".fastmigrate", "w") as f:
                f.write("[paths]\ndb = data/database.db\nmigrations = migrations")
            
            # Run the CLI
            with patch("sys.argv", ["fastmigrate"]):
                result = runner.invoke(app)
            
            assert result.exit_code == 0
            
            # Verify the database was created and migration applied
            db_path = data_path / "database.db"
            assert db_path.exists()
            conn = sqlite3.connect(db_path)
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
        temp_dir_path = Path(temp_dir)
        migrations_dir = temp_dir_path / "custom_migrations"
        db_dir = temp_dir_path / "custom_data"
        migrations_dir.mkdir()
        db_dir.mkdir()
        
        db_path = db_dir / "custom.db"
        
        # Create a migration
        with open(migrations_dir / "0001-test.sql", "w") as f:
            f.write("CREATE TABLE custom (id INTEGER PRIMARY KEY);")
        
        # Run with explicit paths
        result = runner.invoke(app, [
            "--db", str(db_path),
            "--migrations", str(migrations_dir)
        ])
        
        assert result.exit_code == 0
        
        # Verify the database was created and migration applied
        assert db_path.exists()
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
        temp_dir_path = Path(temp_dir)
        migrations_dir = temp_dir_path / "custom_migrations"
        db_dir = temp_dir_path / "custom_data"
        migrations_dir.mkdir()
        db_dir.mkdir()
        
        db_path = db_dir / "custom.db"
        config_path = temp_dir_path / "custom.ini"
        
        # Create a migration
        with open(migrations_dir / "0001-test.sql", "w") as f:
            f.write("CREATE TABLE custom_config (id INTEGER PRIMARY KEY);")
        
        # Create a config file
        with open(config_path, "w") as f:
            f.write(f"[paths]\ndb = {db_path}\nmigrations = {migrations_dir}")
        
        # Run with config file
        result = runner.invoke(app, ["--config", str(config_path)])
        
        assert result.exit_code == 0
        
        # Verify the database was created and migration applied
        assert db_path.exists()
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version FROM _meta")
        assert cursor.fetchone()[0] == 1
        
        # Check the migration was applied
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='custom_config'"
        )
        assert cursor.fetchone() is not None
        
        conn.close()


def test_cli_with_testsuite_a():
    """Test CLI using testsuite_a."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        db_path = temp_dir_path / "test.db"
        
        # Run the CLI with explicit paths to the test suite
        result = runner.invoke(app, [
            "--db", str(db_path),
            "--migrations", str(TESTSUITE_A_DIR / "migrations")
        ])
        
        assert result.exit_code == 0
        
        # Verify the database was created and migrations applied
        assert db_path.exists()
        conn = sqlite3.connect(db_path)
        
        # Version should be 4 (all migrations applied)
        cursor = conn.execute("SELECT version FROM _meta")
        assert cursor.fetchone()[0] == 4
        
        # Verify tables exist
        tables = ["users", "posts", "tags", "post_tags"]
        for table in tables:
            cursor = conn.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
            )
            assert cursor.fetchone() is not None
        
        conn.close()