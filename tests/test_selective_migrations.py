"""Tests for selective migration behavior in fastmigrate."""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fastmigrate.cli import app
from fastmigrate.core import run_migrations, ensure_meta_table


# Path to the selective migrations directory
SELECTIVE_DIR = Path(__file__).parent / "test_selective_migrations"
runner = CliRunner()


def test_selective_migrations_core():
    """Test that only migrations with version > current_version are applied.
    
    This test verifies the core behavior that fastmigrate should only run
    migration scripts with version numbers higher than the current DB version.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        migrations_dir = SELECTIVE_DIR / "migrations"
        # Create empty database file
        conn = sqlite3.connect(db_path)
        conn.close()
        
        # Initialize the database with _meta table
        ensure_meta_table(str(db_path))
        
        # First run: should apply all migrations (0001 through 0010)
        assert run_migrations(str(db_path), str(migrations_dir)) is True
        
        # Check database state after first run
        conn = sqlite3.connect(db_path)
        
        # DB version should be 10 (highest migration)
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        assert cursor.fetchone()[0] == 10
        
        # Verify all migrations were applied (1, 2, 3, 5, 10)
        cursor = conn.execute("SELECT migration_id FROM migrations_log ORDER BY migration_id")
        migration_ids = [row[0] for row in cursor.fetchall()]
        assert migration_ids == [1, 2, 3, 5, 10]
        
        # Create a new test migration with higher version
        temp_migrations_dir = Path(temp_dir) / "migrations"
        temp_migrations_dir.mkdir()
        
        # Copy all existing migrations to temp directory
        for migration_file in migrations_dir.glob("*.*"):
            with open(migration_file, "r") as src:
                with open(temp_migrations_dir / migration_file.name, "w") as dst:
                    dst.write(src.read())
        
        # Add a new migration with version 15
        with open(temp_migrations_dir / "0015-new.sql", "w") as f:
            f.write("""
            INSERT INTO migrations_log (migration_id, description) 
            VALUES (15, 'New migration added after first run');
            """)
        
        # Run migrations again - should only apply the new one
        assert run_migrations(str(db_path), str(temp_migrations_dir)) is True
        
        # Check database state after second run
        # DB version should be 15 now
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        assert cursor.fetchone()[0] == 15
        
        # Verify migration_log now has 1, 2, 3, 5, 10, 15
        cursor = conn.execute("SELECT migration_id FROM migrations_log ORDER BY migration_id")
        migration_ids = [row[0] for row in cursor.fetchall()]
        assert migration_ids == [1, 2, 3, 5, 10, 15]
        
        # No duplicates should be present
        cursor = conn.execute("SELECT migration_id, COUNT(*) FROM migrations_log GROUP BY migration_id HAVING COUNT(*) > 1")
        assert cursor.fetchone() is None
        
        conn.close()


def test_selective_migrations_resume_after_failure():
    """Test that migrations resume correctly after a failure.
    
    This test verifies that if migrations fail at version X, running migrations
    again will correctly start from version X+1.
    """
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
        
        # Create initial migration
        with open(migrations_dir / "0001-initial.sql", "w") as f:
            f.write("""
            CREATE TABLE migrations_log (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );
            INSERT INTO migrations_log (id, name) VALUES (1, 'first');
            """)
        
        # Create a second migration that will succeed
        with open(migrations_dir / "0002-second.sql", "w") as f:
            f.write("""
            INSERT INTO migrations_log (id, name) VALUES (2, 'second');
            """)
        
        # Create a third migration that will fail - make sure it doesn't insert before failing
        with open(migrations_dir / "0003-failing.sql", "w") as f:
            f.write("""
            -- This will cause an error - no data inserted before error
            CREATE TABLE missing_semicolon (id INTEGER PRIMARY KEY
            """)
        
        # Create a fourth migration
        with open(migrations_dir / "0004-fourth.sql", "w") as f:
            f.write("""
            INSERT INTO migrations_log (id, name) VALUES (4, 'fourth');
            """)
        
        # First run: should apply 0001, 0002, and fail at 0003
        assert run_migrations(str(db_path), str(migrations_dir)) is False
        
        # Check database state
        conn = sqlite3.connect(db_path)
        
        # Version should be 2 (last successful migration)
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        assert cursor.fetchone()[0] == 2
        
        # Should have entries for 1 and 2 only
        cursor = conn.execute("SELECT id FROM migrations_log ORDER BY id")
        ids = [row[0] for row in cursor.fetchall()]
        assert ids == [1, 2]
        
        # Remove the failing migration and replace with corrected version
        (migrations_dir / "0003-failing.sql").unlink()  # Delete the failing file
        with open(migrations_dir / "0003-fixed.sql", "w") as f:
            f.write("""
            INSERT INTO migrations_log (id, name) VALUES (3, 'third-fixed');
            """)
        
        # Second run: should start from 0003-fixed.sql
        assert run_migrations(str(db_path), str(migrations_dir)) is True
        
        # Check database state again
        # Version should be 4 now
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        assert cursor.fetchone()[0] == 4
        
        # Should have entries for 1, 2, 3, and 4
        cursor = conn.execute("SELECT id, name FROM migrations_log ORDER BY id")
        results = cursor.fetchall()
        assert len(results) == 4
        assert results[2][0] == 3
        assert results[2][1] == 'third-fixed'
        assert results[3][0] == 4
        
        conn.close()


def test_selective_migrations_with_gaps():
    """Test that migrations with gaps in version numbers work correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        migrations_dir = SELECTIVE_DIR / "migrations"
        # Create empty database file
        conn = sqlite3.connect(db_path)
        conn.close()
        
        # Initialize the database with _meta table
        ensure_meta_table(str(db_path))
        
        # Run migrations
        assert run_migrations(str(db_path), str(migrations_dir)) is True
        
        # Check database state
        conn = sqlite3.connect(db_path)
        
        # DB version should be 10 (highest migration)
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        assert cursor.fetchone()[0] == 10
        
        # Verify gaps in migration_ids (no 4, 6-9)
        cursor = conn.execute("SELECT migration_id FROM migrations_log ORDER BY migration_id")
        migration_ids = [row[0] for row in cursor.fetchall()]
        assert migration_ids == [1, 2, 3, 5, 10]
        
        conn.close()


def test_cli_selective_migrations():
    """Test selective migrations via the CLI interface."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        # Create empty database file
        conn = sqlite3.connect(db_path)
        conn.close()
        
        # Initialize the database with _meta table
        ensure_meta_table(str(db_path))
        
        # Create a temporary migrations directory with just one initial migration
        migrations_dir = Path(temp_dir) / "migrations"
        migrations_dir.mkdir()
        
        # Create initial migration
        with open(migrations_dir / "0001-initial.sql", "w") as f:
            f.write("""
            CREATE TABLE migrations_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_id INTEGER NOT NULL,
                description TEXT NOT NULL
            );
            INSERT INTO migrations_log (migration_id, description) 
            VALUES (1, 'Initial migration');
            """)
        
        # Run first migration only
        result = runner.invoke(app, [
            "--db", str(db_path),
            "--migrations", str(migrations_dir)
        ])
        assert result.exit_code == 0
        
        # Check that only migration 1 was applied
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        assert cursor.fetchone()[0] == 1
        cursor = conn.execute("SELECT migration_id FROM migrations_log")
        assert cursor.fetchone()[0] == 1
        assert cursor.fetchone() is None  # No more rows
        
        # Manually update the version to 5
        conn.execute("UPDATE _meta SET version = 5 WHERE id = 1")
        conn.commit()
        conn.close()
        
        # Now add a new migration with version 10
        with open(migrations_dir / "0010-tenth.py", "w") as f:
            f.write("""#!/usr/bin/env python
import sqlite3
import sys

def main():
    db_path = sys.argv[1]
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO migrations_log (migration_id, description) VALUES (10, 'Tenth migration')")
    conn.commit()
    conn.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
            """)
        
        # Make it executable
        (migrations_dir / "0010-tenth.py").chmod(0o755)
        
        # Second run: should skip migrations with versions <= 5 and only apply 0010
        result = runner.invoke(app, [
            "--db", str(db_path),
            "--migrations", str(migrations_dir)
        ])
        assert result.exit_code == 0
        
        # Verify the final state
        conn = sqlite3.connect(db_path)
        
        # DB version should be 10
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        assert cursor.fetchone()[0] == 10
        
        # Verify log has entries for migrations 1 and 10 only
        cursor = conn.execute("SELECT migration_id FROM migrations_log ORDER BY migration_id")
        migration_ids = [row[0] for row in cursor.fetchall()]
        assert migration_ids == [1, 10]  # Only 1 and 10, not 5 (since we skipped it)
        
        conn.close()