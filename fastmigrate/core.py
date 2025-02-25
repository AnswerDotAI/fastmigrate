"""Core functionality for fastmigrate."""

import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def ensure_meta_table(conn: sqlite3.Connection) -> None:
    """Create the _meta table if it doesn't exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _meta (
            version INTEGER NOT NULL
        )
        """
    )
    # Check if there's a row and insert version 0 if not
    cursor = conn.execute("SELECT COUNT(*) FROM _meta")
    if cursor.fetchone()[0] == 0:
        conn.execute("INSERT INTO _meta (version) VALUES (0)")
    # Ensure there's only one row
    cursor = conn.execute("SELECT COUNT(*) FROM _meta")
    if cursor.fetchone()[0] > 1:
        conn.execute("DELETE FROM _meta")
        conn.execute("INSERT INTO _meta (version) VALUES (0)")
    conn.commit()


def get_db_version(conn: sqlite3.Connection) -> int:
    """Get the current database version."""
    cursor = conn.execute("SELECT version FROM _meta LIMIT 1")
    return cursor.fetchone()[0]


def set_db_version(conn: sqlite3.Connection, version: int) -> None:
    """Set the database version."""
    conn.execute("UPDATE _meta SET version = ?", (version,))
    conn.commit()


def extract_version_from_filename(filename: str) -> Optional[int]:
    """Extract the version number from a migration script filename."""
    match = re.match(r"^(\d{4})-.*\.(py|sql|sh)$", filename)
    if match:
        return int(match.group(1))
    return None


def get_migration_scripts(migrations_dir: str) -> Dict[int, str]:
    """Get all valid migration scripts from the migrations directory.
    
    Returns a dictionary mapping version numbers to file paths.
    Raises ValueError if two scripts have the same version number.
    """
    migration_scripts: Dict[int, str] = {}
    
    if not os.path.exists(migrations_dir):
        return migration_scripts
    
    for filename in os.listdir(migrations_dir):
        version = extract_version_from_filename(filename)
        if version is not None:
            filepath = os.path.join(migrations_dir, filename)
            if version in migration_scripts:
                raise ValueError(
                    f"Duplicate migration version {version}: "
                    f"{migration_scripts[version]} and {filepath}"
                )
            migration_scripts[version] = filepath
    
    return migration_scripts


def execute_sql_script(db_path: str, script_path: str) -> bool:
    """Execute a SQL script against the database."""
    try:
        result = subprocess.run(
            ["sqlite3", db_path],
            input=Path(script_path).read_bytes(),
            capture_output=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing SQL script {script_path}:", file=sys.stderr)
        print(e.stderr.decode(), file=sys.stderr)
        return False


def execute_python_script(db_path: str, script_path: str) -> bool:
    """Execute a Python script."""
    try:
        result = subprocess.run(
            [sys.executable, script_path, db_path],
            capture_output=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing Python script {script_path}:", file=sys.stderr)
        print(e.stderr.decode(), file=sys.stderr)
        return False


def execute_shell_script(db_path: str, script_path: str) -> bool:
    """Execute a shell script."""
    try:
        result = subprocess.run(
            ["sh", script_path, db_path],
            capture_output=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing shell script {script_path}:", file=sys.stderr)
        print(e.stderr.decode(), file=sys.stderr)
        return False


def execute_migration_script(db_path: str, script_path: str) -> bool:
    """Execute a migration script based on its file extension."""
    ext = os.path.splitext(script_path)[1].lower()
    
    if ext == ".sql":
        return execute_sql_script(db_path, script_path)
    elif ext == ".py":
        return execute_python_script(db_path, script_path)
    elif ext == ".sh":
        return execute_shell_script(db_path, script_path)
    else:
        print(f"Unsupported script type: {script_path}", file=sys.stderr)
        return False


def run_migrations(db_path: str, migrations_dir: str) -> bool:
    """Run all pending migrations.
    
    Returns True if all migrations succeed, False otherwise.
    """
    # Connect to the database
    conn = sqlite3.connect(db_path)
    try:
        # Ensure _meta table exists
        ensure_meta_table(conn)
        
        # Get current version
        current_version = get_db_version(conn)
        
        # Get all migration scripts
        try:
            migration_scripts = get_migration_scripts(migrations_dir)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return False
        
        # Find pending migrations
        pending_migrations = {
            version: path
            for version, path in migration_scripts.items()
            if version > current_version
        }
        
        if not pending_migrations:
            print(f"Database is up to date (version {current_version})")
            return True
        
        # Sort migrations by version
        sorted_versions = sorted(pending_migrations.keys())
        
        # Execute migrations
        for version in sorted_versions:
            script_path = pending_migrations[version]
            print(f"Applying migration {version}: {os.path.basename(script_path)}")
            
            if not execute_migration_script(db_path, script_path):
                print(f"Migration failed: {script_path}", file=sys.stderr)
                return False
            
            # Update database version
            set_db_version(conn, version)
            print(f"Database updated to version {version}")
        
        return True
    
    finally:
        conn.close()