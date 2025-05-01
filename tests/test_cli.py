"""Tests for the CLI interface."""

import os
import sqlite3
import tempfile
from pathlib import Path
import io
import sys
from unittest.mock import patch
import subprocess

from fastmigrate.cli import backup_db, check_version, create_db, run_migrations
from fastmigrate.core import _ensure_meta_table, _set_db_version

# Path to the test migrations directory
CLI_MIGRATIONS_DIR = Path(__file__).parent / "test_cli"


def test_cli_help_backup_db():
    """Test the CLI help output for ."""
    # Capture standard output
    result = subprocess.run(['fastmigrate_backup_db', '--help'], 
                           capture_output=True, text=True)
    assert result.returncode == 0                           
    assert "usage: fastmigrate_backup_db [-h] [--db DB]" in result.stdout

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
        
        # Initialize the database with _meta table
        _ensure_meta_table(db_path)
        
        # Create a migration
        with open(migrations_dir / "0001-test.sql", "w") as f:
            f.write("CREATE TABLE custom (id INTEGER PRIMARY KEY);")
        
        # Run with explicit paths
        result = subprocess.run([
            "fastmigrate_run_migrations",
            "--db", db_path,
            "--migrations", migrations_dir
        ])
        
        assert result.returncode == 0
        
        # Verify migration was applied
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version FROM _meta")
        assert cursor.fetchone()[0] == 1
        
        # Check the migration was applied
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='custom'")
        assert cursor.fetchone() is not None
        
        conn.close()


def test_cli_backup_option():
    """Test CLI with the --backup option."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        db_path = temp_dir_path / "test.db"
        migrations_path = temp_dir_path / "migrations"
        migrations_path.mkdir()
        
        # Create a database with initial data
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE initial (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO initial (value) VALUES ('initial data')")
        conn.commit()
        conn.close()
        
        # Initialize the database with _meta table
        _ensure_meta_table(db_path)
        
        # Create a test migration
        with open(migrations_path / "0001-test.sql", "w") as f:
            f.write("CREATE TABLE test (id INTEGER PRIMARY KEY);")
        
        # Run the backup
        result = subprocess.run([
            "fastmigrate_backup_db",
            "--db", db_path
        ])

        # Run the migration
        result = subprocess.run([
            "fastmigrate_run_migrations",
            "--db", db_path,
            "--migrations", migrations_path,
        ])
        
        assert result.returncode == 0
        
        # Check that a backup file was created
        backup_files = list(temp_dir_path.glob("*.backup"))
        assert len(backup_files) == 1
        backup_path = backup_files[0]
        
        # Verify the backup has the initial data but not the migration
        conn_backup = sqlite3.connect(backup_path)
        
        # Should have the initial table with data
        cursor = conn_backup.execute("SELECT value FROM initial")
        assert cursor.fetchone()[0] == "initial data"
        
        # Should NOT have the test table from the migration
        cursor = conn_backup.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test'")
        assert cursor.fetchone() is None
        
        # But the original DB should have both tables
        conn = sqlite3.connect(db_path)
        
        # Original should have the initial table
        cursor = conn.execute("SELECT value FROM initial")
        assert cursor.fetchone()[0] == "initial data"
        
        # Original should have the test table from the migration
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test'")
        assert cursor.fetchone() is not None
        
        conn_backup.close()
        conn.close()


def test_cli_config_file():
    """Test CLI with configuration from file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        # Create custom directories
        migrations_dir = temp_dir / "custom_migrations"
        db_dir = temp_dir / "custom_data"
        migrations_dir.mkdir()
        db_dir.mkdir()
        
        db_path = db_dir / "custom.db"
        config_path = temp_dir / "custom.ini"
        
        # Create empty database file
        conn = sqlite3.connect(db_path)
        conn.close()
        
        # Initialize the database with _meta table
        _ensure_meta_table(db_path)
        
        # Create a migration
        (migrations_dir / "0001-test.sql").write_text("CREATE TABLE custom_config (id INTEGER PRIMARY KEY);")
        
        # Create a config file
        config_path.write_text(f"[paths]\ndb = {db_path}\nmigrations = {migrations_dir}")

        # Run with config file
        result = subprocess.run(["fastmigrate_run_migrations", "--config", config_path])

        assert result.returncode == 0
        
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


def test_cli_precedence():
    """Test that CLI arguments take precedence over config file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        
        # Create multiple directories to test precedence
        migrations_config = temp_dir_path / "config_migrations"
        migrations_cli = temp_dir_path / "cli_migrations"
        db_dir_config = temp_dir_path / "config_db_dir"
        db_dir_cli = temp_dir_path / "cli_db_dir"
        
        migrations_config.mkdir()
        migrations_cli.mkdir()
        db_dir_config.mkdir()
        db_dir_cli.mkdir()
        
        db_path_config = db_dir_config / "config.db"
        db_path_cli = db_dir_cli / "cli.db"
        config_path = temp_dir_path / "precedence.ini"
        
        # Create empty database files
        for db in [db_path_config, db_path_cli]:
            conn = sqlite3.connect(db)
            conn.close()
            # Initialize the database with _meta table
            _ensure_meta_table(db)
        
        # Create different migrations in each directory
        with open(migrations_config / "0001-config.sql", "w") as f:
            f.write("CREATE TABLE config_table (id INTEGER PRIMARY KEY);")
        
        with open(migrations_cli / "0001-cli.sql", "w") as f:
            f.write("CREATE TABLE cli_table (id INTEGER PRIMARY KEY);")
        
        # Create a config file with specific paths
        with open(config_path, "w") as f:
            f.write(f"[paths]\ndb = {db_path_config}\nmigrations = {migrations_config}")
        
        # Run with BOTH config file AND explicit CLI args
        # CLI args should take precedence
        result = subprocess.run([
            "fastmigrate_run_migrations",
            "--config", config_path,
            "--db", db_path_cli,
            "--migrations", migrations_cli
        ])
        
        assert result.returncode == 0
        
        # Verify migration was applied to the CLI database, not the config one
        # Config DB should be untouched
        conn_config = sqlite3.connect(db_path_config)
        cursor = conn_config.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='config_table'")
        assert cursor.fetchone() is None, "Config DB should not have config_table"
        conn_config.close()
        
        # CLI DB should have the CLI migration applied
        conn_cli = sqlite3.connect(db_path_cli)
        cursor = conn_cli.execute("SELECT version FROM _meta")
        assert cursor.fetchone()[0] == 1, "CLI DB should have version 1"
        
        cursor = conn_cli.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cli_table'")
        assert cursor.fetchone() is not None, "CLI DB should have cli_table"
        
        cursor = conn_cli.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='config_table'")
        assert cursor.fetchone() is None, "CLI DB should not have config_table"
        
        conn_cli.close()
        



def test_cli_createdb_flag():
    """Test the --create_db flag properly initializes a database with _meta table."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        db_path = temp_dir_path / "new_db.db"
        
        # Verify the database doesn't exist yet
        assert not db_path.exists()
        
        # Run the CLI with just the --create_db flag
        result = subprocess.run([
            "fastmigrate_create_db",
            "--db", db_path,
        ])
        
        assert result.returncode == 0
        
        # Verify database was created
        assert db_path.exists()
        
        # Verify the _meta table exists with version 0
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='_meta'")
        assert cursor.fetchone() is not None
        
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        assert cursor.fetchone()[0] == 0
        
        conn.close()


def test_check_db_version_option():
    """Test the --check_db_version option correctly reports the database version."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        db_path = temp_dir_path / "test.db"
        
        # Create database file with version 42
        conn = sqlite3.connect(db_path)
        conn.close()
        _ensure_meta_table(db_path)
        _set_db_version(db_path, 42)
        
        # Test with versioned database
        result = subprocess.run([
            "fastmigrate_check_version",
            "--db", db_path
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert "Database version: 42" in result.stdout
        
        # Create unversioned database
        unversioned_db = temp_dir_path / "unversioned.db"
        conn = sqlite3.connect(unversioned_db)
        conn.close()
        
        # Test with unversioned database
        result = subprocess.run([
            "fastmigrate_check_version",            
            "--db", unversioned_db,
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert "unversioned" in result.stdout.lower()
        
        # Test with non-existent database
        nonexistent_db = temp_dir_path / "nonexistent.db"
        result = subprocess.run([
            "fastmigrate_check_version",            
            "--db", nonexistent_db,
        ], capture_output=True, text=True)
        
        assert result.returncode == 1
        assert "does not exist" in result.stdout


def test_cli_with_testsuite_a():
    """Test CLI using testsuite_a."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        db_path = temp_dir_path / "test.db"
        
        # Create empty database file
        conn = sqlite3.connect(db_path)
        conn.close()
        
        # Initialize the database with _meta table
        _ensure_meta_table(db_path)
        
        # Run the CLI with explicit paths to the test suite
        result = subprocess.run([
            "fastmigrate_run_migrations",
            "--db", db_path,
            "--migrations", CLI_MIGRATIONS_DIR / "migrations"
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        
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
