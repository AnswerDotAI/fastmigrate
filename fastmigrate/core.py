"""Core functionality for fastmigrate."""

import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional


def ensure_meta_table(conn: sqlite3.Connection) -> None:
    """Create the _meta table if it doesn't exist, with a single row constraint.
    
    Uses a single-row pattern with a PRIMARY KEY on a constant value (1).
    This ensures we can only have one row in the table.
    """
    # Check if _meta table exists
    cursor = conn.execute(
        """
        SELECT name, sql FROM sqlite_master 
        WHERE type='table' AND name='_meta'
        """
    )
    row = cursor.fetchone()
    
    if row is None:
        # Table doesn't exist, create new format
        with conn:
            conn.execute(
                """
                CREATE TABLE _meta (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    version INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute("INSERT INTO _meta (id, version) VALUES (1, 0)")
    
    elif "id" not in row[1]:
        # Table exists in old format, migrate to new format
        try:
            # Get current version from old format
            cursor = conn.execute("SELECT version FROM _meta LIMIT 1")
            result = cursor.fetchone()
            current_version = result[0] if result else 0
            
            # Create a new table with the correct schema
            try:
                # Try to handle migration in a single atomic operation
                conn.execute("ALTER TABLE _meta RENAME TO _meta_old")
                conn.execute(
                    """
                    CREATE TABLE _meta (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        version INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                conn.execute("INSERT INTO _meta (id, version) VALUES (1, ?)", (current_version,))
                conn.execute("DROP TABLE _meta_old")
                conn.commit()
            except Exception:
                # If an error occurred, roll back
                conn.rollback()
        except Exception as e:
            print(f"Error migrating _meta table: {e}", file=sys.stderr)
            # If migration fails, create a new table with version 0
            with conn:
                conn.execute("DROP TABLE IF EXISTS _meta")
                conn.execute(
                    """
                    CREATE TABLE _meta (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        version INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                conn.execute("INSERT INTO _meta (id, version) VALUES (1, 0)")
    
    # If table exists in new format, do nothing


def get_db_version(conn: sqlite3.Connection) -> int:
    """Get the current database version."""
    cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
    result = cursor.fetchone()
    if result is None:
        # This should never happen due to constraints, but just in case
        ensure_meta_table(conn)
        return 0
    return result[0]


def set_db_version(conn: sqlite3.Connection, version: int) -> None:
    """Set the database version.
    
    Uses an UPSERT pattern (INSERT OR REPLACE) to ensure we always set the 
    version for id=1, even if the row doesn't exist yet.
    """
    conn.execute(
        """
        INSERT OR REPLACE INTO _meta (id, version) 
        VALUES (1, ?)
        """, 
        (version,)
    )
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


def create_db_backup(db_path: str) -> str:
    """Create a backup of the database.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        str: Path to the backup file
    """
    backup_path = f"{db_path}.backup"
    shutil.copy2(db_path, backup_path)
    return backup_path


def restore_db_backup(backup_path: str, db_path: str) -> bool:
    """Restore database from backup.
    
    Args:
        backup_path: Path to the backup file
        db_path: Path to the target database file
        
    Returns:
        bool: True if restore was successful, False otherwise
    """
    try:
        # If the DB file exists, remove it first
        if os.path.exists(db_path):
            os.remove(db_path)
        
        # Copy the backup back to the original location
        shutil.copy2(backup_path, db_path)
        
        # Remove the backup file
        os.remove(backup_path)
        
        return True
    except Exception as e:
        print(f"Error restoring database backup: {e}", file=sys.stderr)
        return False


def execute_sql_script(db_path: str, script_path: str) -> bool:
    """Execute a SQL script against the database.
    
    Args:
        db_path: Path to the SQLite database file
        script_path: Path to the SQL script file
        
    Returns:
        bool: True if the script executed successfully, False otherwise
    """
    # Connect directly to the database
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        
        # Read script content
        script_content = Path(script_path).read_text()
        
        # Execute the script
        conn.executescript(script_content)
        return True
        
    except sqlite3.Error as e:
        # SQL error occurred
        print(f"Error executing SQL script {script_path}:", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        return False
    
    except Exception as e:
        # Handle other errors (file not found, etc.)
        print(f"Error executing SQL script {script_path}:", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        return False
        
    finally:
        if conn:
            conn.close()


def execute_python_script(db_path: str, script_path: str) -> bool:
    """Execute a Python script."""
    try:
        subprocess.run(
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
        subprocess.run(
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
    
    Uses a backup/restore approach for rollback:
    1. Before each migration, backs up the database
    2. If migration fails, restores from backup
    3. If migration succeeds, removes backup and updates version
    
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
            script_name = os.path.basename(script_path)
            print(f"Applying migration {version}: {script_name}")
            
            # Create a backup before executing the script
            backup_path = create_db_backup(db_path)
            
            # Close the connection before running the script
            # Each script will open its own connection
            conn.close()
            conn = None
            
            # Execute the migration script
            success = execute_migration_script(db_path, script_path)
            
            if not success:
                print(f"Migration failed: {script_path}", file=sys.stderr)
                print("Restoring database from backup...", file=sys.stderr)
                
                # Restore from backup
                if restore_db_backup(backup_path, db_path):
                    print("Database restored successfully", file=sys.stderr)
                else:
                    print("WARNING: Failed to restore database from backup", file=sys.stderr)
                
                return False
            
            # Remove backup after successful migration
            if os.path.exists(backup_path):
                os.remove(backup_path)
            
            # Reopen connection and update version
            conn = sqlite3.connect(db_path)
            set_db_version(conn, version)
            print(f"Database updated to version {version}")
        
        return True
    
    finally:
        if conn:
            conn.close()