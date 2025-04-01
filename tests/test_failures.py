"""Tests for failure handling in fastmigrate."""

import sqlite3
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fastmigrate.cli import app
from fastmigrate.core import run_migrations, ensure_meta_table


# Path to the migrations directory
FAILURES_DIR = Path(__file__).parent / "test_failures"
runner = CliRunner()


def test_sql_failure():
    """Test handling of SQL script failure."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        migrations_dir = FAILURES_DIR / "migrations"
        
        # Create empty database file
        conn = sqlite3.connect(db_path)
        conn.close()
        
        # Initialize the database with _meta table
        ensure_meta_table(str(db_path))
        
        # Run migrations - should fail on the second migration
        result = run_migrations(str(db_path), str(migrations_dir))
        assert result is False
        
        # Connect to the database and check the version
        # It should be at version 1 (first migration succeeded)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version FROM _meta")
        assert cursor.fetchone()[0] == 1
        
        # Check that the first migration was applied and we have table
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
        assert cursor.fetchone() is not None
        
        # Check the first two rows were inserted (from first migration)
        cursor = conn.execute("SELECT name FROM test_table WHERE name IN ('test1', 'test2')")
        results = cursor.fetchall()
        assert len(results) == 2
        
        # Check we don't have the table from the failed migration
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='this_syntax_error'")
        assert cursor.fetchone() is None
        
        conn.close()


def test_cli_sql_failure():
    """Test CLI handling of SQL script failure."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        
        # Create empty database file
        conn = sqlite3.connect(db_path)
        conn.close()
        
        # Initialize the database with _meta table
        ensure_meta_table(str(db_path))
        
        # Run the CLI with path to the failure test suite
        result = runner.invoke(app, [
            "--db", str(db_path),
            "--migrations", str(FAILURES_DIR / "migrations")
        ])
        
        # CLI should exit with non-zero code
        assert result.exit_code != 0
        
        # Check that only one migration was applied
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version FROM _meta")
        assert cursor.fetchone()[0] == 1
        
        conn.close()


def test_python_failure():
    """Test handling of Python script failure."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        migrations_dir = Path(temp_dir) / "migrations"
        migrations_dir.mkdir()
        
        # Create empty database file
        conn = sqlite3.connect(db_path)
        conn.close()
        
        # Initialize the database with _meta table
        ensure_meta_table(str(db_path))
        
        # Create a test database with initial successful migration
        initial_migration = migrations_dir / "0001-init.sql"
        with open(initial_migration, "w") as f:
            f.write("CREATE TABLE test (id INTEGER PRIMARY KEY);")
        
        # Create a Python migration that will fail
        python_migration = migrations_dir / "0002-fail.py"
        with open(python_migration, "w") as f:
            f.write("""#!/usr/bin/env python
import sys
print("Failing intentionally")
sys.exit(1)
""")
        
        # Make the Python script executable
        python_migration.chmod(0o755)
        
        # Run migrations - should fail on the Python script
        result = run_migrations(str(db_path), str(migrations_dir))
        assert result is False
        
        # Connect to the database and check the version
        # It should be at version 1 (first migration succeeded)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version FROM _meta")
        assert cursor.fetchone()[0] == 1
        
        conn.close()


def test_shell_failure():
    """Test handling of shell script failure."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        migrations_dir = Path(temp_dir) / "migrations"
        migrations_dir.mkdir()
        
        # Create empty database file
        conn = sqlite3.connect(db_path)
        conn.close()
        
        # Initialize the database with _meta table
        ensure_meta_table(str(db_path))
        
        # Create a test database with initial successful migration
        initial_migration = migrations_dir / "0001-init.sql"
        with open(initial_migration, "w") as f:
            f.write("CREATE TABLE test (id INTEGER PRIMARY KEY);")
        
        # Create a shell script that will fail
        shell_migration = migrations_dir / "0002-fail.sh"
        with open(shell_migration, "w") as f:
            f.write("""#!/bin/sh
echo "Failing intentionally"
exit 2
""")
        
        # Make the shell script executable
        shell_migration.chmod(0o755)
        
        # Run migrations - should fail on the shell script
        result = run_migrations(str(db_path), str(migrations_dir))
        assert result is False
        
        # Connect to the database and check the version
        # It should be at version 1 (first migration succeeded)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version FROM _meta")
        assert cursor.fetchone()[0] == 1
        
        conn.close()


def test_testsuite_failure_cli():
    """Test CLI with the failure test suite."""
    # Test each migration type failure using separate databases
    migration_files = [
        {"file": "0002-sql-failure.sql", "expected_version": 1},
        {"file": "0003-python-failure.py", "expected_version": 1},
        {"file": "0004-shell-failure.sh", "expected_version": 1},
    ]
    
    for migration in migration_files:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            
            # Create empty database file
            conn = sqlite3.connect(db_path)
            conn.close()
            
            # Initialize the database with _meta table
            ensure_meta_table(str(db_path))
            
            # Create a temporary migrations directory with just the successful migration
            # and the specific failure migration we want to test
            migrations_dir = Path(temp_dir) / "migrations"
            migrations_dir.mkdir()
            
            # Copy the successful first migration
            with open(FAILURES_DIR / "migrations" / "0001-initial-setup.sql", "r") as src:
                with open(migrations_dir / "0001-initial-setup.sql", "w") as dst:
                    dst.write(src.read())
            
            # Copy the specific failure migration
            with open(FAILURES_DIR / "migrations" / migration["file"], "r") as src:
                with open(migrations_dir / migration["file"], "w") as dst:
                    dst.write(src.read())
            
            # Make executable if needed
            if migration["file"].endswith((".py", ".sh")):
                (migrations_dir / migration["file"]).chmod(0o755)
            
            # Run the CLI
            result = runner.invoke(app, [
                "--db", str(db_path),
                "--migrations", str(migrations_dir)
            ])
            
            # CLI should exit with non-zero code
            assert result.exit_code != 0, f"Expected failure for {migration['file']}"
            
            # Check that the database was created but only one migration applied
            assert db_path.exists()
            conn = sqlite3.connect(db_path)
            cursor = conn.execute("SELECT version FROM _meta")
            assert cursor.fetchone()[0] == migration["expected_version"], \
                f"Wrong version for {migration['file']}"
            
            conn.close()