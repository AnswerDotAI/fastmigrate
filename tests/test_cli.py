"""Tests for the CLI interface."""

import os
import sqlite3
import tempfile
from pathlib import Path
import io
import sys
from unittest.mock import patch

from typer.testing import CliRunner

from fastmigrate.cli import app


runner = CliRunner()

# Path to the test migrations directory
CLI_MIGRATIONS_DIR = Path(__file__).parent / "test_cli"


def test_cli_help():
    """Test the CLI help output."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # The help text moved to the docstring of the main function
    # After our refactoring, this might be displayed differently
    assert "Structured migration of data in SQLite databases" in result.stdout


def test_cli_defaults():
    """Test CLI with default arguments."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create paths in the temporary directory
        temp_dir_path = Path(temp_dir)
        migrations_path = temp_dir_path / "migrations"
        data_path = temp_dir_path / "data"
        migrations_path.mkdir()
        data_path.mkdir()
        
        # Create empty database file
        db_path = data_path / "database.db"
        conn = sqlite3.connect(db_path)
        conn.close()
        
        # Create a test migration
        with open(migrations_path / "0001-test.sql", "w") as f:
            f.write("CREATE TABLE test (id INTEGER PRIMARY KEY);")
        
        # Create a config file
        with open(temp_dir_path / ".fastmigrate", "w") as f:
            f.write("[paths]\ndb = data/database.db\nmigrations = migrations")
        
        # Store original directory and change to temp directory
        # so defaults resolve relative to it
        original_dir = os.getcwd()
        os.chdir(temp_dir_path)
        
        try:
            # Run the CLI
            with patch("sys.argv", ["fastmigrate"]):
                result = runner.invoke(app)
            
            assert result.exit_code == 0
            
            # Verify migration was applied
            conn = sqlite3.connect(db_path)
            cursor = conn.execute("SELECT version FROM _meta")
            assert cursor.fetchone()[0] == 1
            
            # Check the migration was applied
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test'")
            assert cursor.fetchone() is not None
            
            conn.close()
        
        finally:
            # ALWAYS return to original directory, even if test fails
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
        
        # Create empty database file
        conn = sqlite3.connect(db_path)
        conn.close()
        
        # Create a migration
        with open(migrations_dir / "0001-test.sql", "w") as f:
            f.write("CREATE TABLE custom (id INTEGER PRIMARY KEY);")
        
        # Run with explicit paths
        result = runner.invoke(app, [
            "--db", str(db_path),
            "--migrations", str(migrations_dir)
        ])
        
        assert result.exit_code == 0
        
        # Verify migration was applied
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
        
        # Create empty database file
        conn = sqlite3.connect(db_path)
        conn.close()
        
        # Create a migration
        with open(migrations_dir / "0001-test.sql", "w") as f:
            f.write("CREATE TABLE custom_config (id INTEGER PRIMARY KEY);")
        
        # Create a config file
        with open(config_path, "w") as f:
            f.write(f"[paths]\ndb = {db_path}\nmigrations = {migrations_dir}")
        
        # Run with config file
        result = runner.invoke(app, ["--config", str(config_path)])
        
        assert result.exit_code == 0
        
        # Verify migration was applied
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version FROM _meta")
        assert cursor.fetchone()[0] == 1
        
        # Check the migration was applied
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='custom_config'"
        )
        assert cursor.fetchone() is not None
        
        conn.close()
        

def test_dry_run():
    """Test dry run mode."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        db_path = temp_dir_path / "test.db"
        migrations_dir = temp_dir_path / "migrations"
        migrations_dir.mkdir()
        
        # Create a database with version 0
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE _meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute("INSERT INTO _meta (id, version) VALUES (1, 0)")
        conn.commit()
        conn.close()
        
        # Create migration scripts
        with open(migrations_dir / "0001-first.sql", "w") as f:
            f.write("CREATE TABLE test1 (id INTEGER PRIMARY KEY);")
        
        with open(migrations_dir / "0002-second.sql", "w") as f:
            f.write("CREATE TABLE test2 (id INTEGER PRIMARY KEY);")
        
        # Run in dry run mode
        result = runner.invoke(
            app, ["--db", str(db_path), "--migrations", str(migrations_dir), "--dry-run"]
        )
        
        # Check output
        assert result.exit_code == 0
        assert "Dry run: Would apply 2 migrations" in result.stdout
        assert "Would apply migration 1: 0001-first.sql" in result.stdout
        assert "Would apply migration 2: 0002-second.sql" in result.stdout
        
        # Verify that no changes were actually made
        conn = sqlite3.connect(db_path)
        
        # Version should still be 0
        cursor = conn.execute("SELECT version FROM _meta")
        assert cursor.fetchone()[0] == 0
        
        # No tables should have been created
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('test1', 'test2')"
        )
        assert len(cursor.fetchall()) == 0
        
        conn.close()


def test_cli_with_testsuite_a():
    """Test CLI using testsuite_a."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        db_path = temp_dir_path / "test.db"
        
        # Create empty database file
        conn = sqlite3.connect(db_path)
        conn.close()
        
        # Run the CLI with explicit paths to the test suite
        result = runner.invoke(app, [
            "--db", str(db_path),
            "--migrations", str(CLI_MIGRATIONS_DIR / "migrations")
        ])
        
        assert result.exit_code == 0
        
        # Verify migrations applied
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