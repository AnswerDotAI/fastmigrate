"""Core functionality for fastmigrate."""

import os
import re
import sqlite3
import subprocess
import sys
from sys import stderr
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from io import StringIO
from apsw import Connection
from apsw.shell import Shell


__all__ = ["run_migrations", "create_db", "get_db_version", "create_db_backup",
           # deprecated
           "ensure_versioned_db",
           "create_database_backup"]

def create_db(db_path:Path) -> int:
    """Creates a versioned db, or ensures the existing db is versioned.

    If no db exists, creates an EMPTY db with version 0. (This is ready
    to be initalized by migration script with version 1.)

    If a db exists, which already has a version, does nothing.

    If a db exists, without a version, raises an sqlite3.Error
    """
    db_path = Path(db_path)
    if not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.close()
        _ensure_meta_table(db_path)
        return 0
    else:
        return get_db_version(db_path)


def ensure_versioned_db(db_path:Path) -> int:
    "See create_db"
    warnings.warn("ensure_versioned_db is deprecated, as it has been renamed to create_db, which is functionally identical",
                 DeprecationWarning,
                  stacklevel=2)
    return create_db(db_path)

def _ensure_meta_table(db_path: Path) -> None:
    """Create the _meta table if it doesn't exist, with a single row constraint.
    
    Uses a single-row pattern with a PRIMARY KEY on a constant value (1).
    This ensures we can only have one row in the table.

    WARNING: users should call this directly only if preparing a
    versioned db manually, for instance, for testing or for enrolling
    a non-version db after verifying its values and schema are what
    would be produced by migration scripts.
    
    Args:
        db_path: Path to the SQLite database
        
    Raises:
        FileNotFoundError: If database file doesn't exist
        sqlite3.Error: If unable to read or write to the database

    """
    db_path = Path(db_path)
    # First check if the file exists
    if not db_path.exists():
        raise FileNotFoundError(f"Database file does not exist: {db_path}")
    
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        # Check if _meta table exists
        cursor = conn.execute(
            """
            SELECT name, sql FROM sqlite_master 
            WHERE type='table' AND name='_meta'
            """
        )
        row = cursor.fetchone()
        
        if row is None:
            # Table doesn't exist, create it with version 0
            try:
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
                    print('Database is enrolled')
            except sqlite3.Error as e:
                raise sqlite3.Error(f"Failed to create _meta table: {e}")
    except sqlite3.Error as e:
        raise sqlite3.Error(f"Failed to access database: {e}")
    finally:
        if conn:
            conn.close()


def get_db_version(db_path: Path) -> int:
    """Get the current database version.
    
    Args:
        db_path: Path to the SQLite database
        
    Returns:
        int: The current database version
        
    Raises:
        FileNotFoundError: If database file doesn't exist
        sqlite3.Error: If unable to read the db version because it is not managed
    """
    db_path = Path(db_path)
    # First check if the file exists
    if not db_path.exists():
        raise FileNotFoundError(f"Database file does not exist: {db_path}")
    
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        result = cursor.fetchone()
        if result is None:
            raise sqlite3.Error("No version found in _meta table")
        return int(result[0])
    except sqlite3.OperationalError:
        raise sqlite3.Error("_meta table does not exist")
    except sqlite3.Error as e:
        raise sqlite3.Error(f"Failed to get database version: {e}")
    finally:
        if conn:
            conn.close()


def _set_db_version(db_path: Path, version: int) -> None:
    """Set the database version.
    
    Uses an UPSERT pattern (INSERT OR REPLACE) to ensure we always set the 
    version for id=1, even if the row doesn't exist yet.
    
    Args:
        db_path: Path to the SQLite database
        version: The version number to set
        
    Raises:
        FileNotFoundError: If database file doesn't exist
        sqlite3.Error: If unable to write to the database
    """
    db_path = Path(db_path)
    # First check if the file exists
    if not db_path.exists():
        raise FileNotFoundError(f"Database file does not exist: {db_path}")
    
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO _meta (id, version) 
                    VALUES (1, ?)
                    """, 
                    (version,)
                )
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Failed to set version: {e}")
    except sqlite3.Error as e:
        raise sqlite3.Error(f"Failed to access database: {e}")
    finally:
        if conn:
            conn.close()


def extract_version_from_filename(filename: str) -> Optional[int]:
    """Extract the version number from a migration script filename."""
    filename = str(filename) # Force Path objects to string
    match = re.match(r"^(\d{4})-.*\.(py|sql|sh)$", filename)
    if match:
        return int(match.group(1))
    return None


def get_migration_scripts(migrations_dir: Path) -> Dict[int, Path]:
    """Get all valid migration scripts from the migrations directory.
    
    Returns a dictionary mapping version numbers to file paths.
    Raises ValueError if two scripts have the same version number.
    """
    migrations_dir = Path(migrations_dir)
    migration_scripts: Dict[int, Path] = {}
    if not migrations_dir.exists():
        return migration_scripts
    
    for file_path in [x for x in migrations_dir.iterdir() if x.is_file()]:
        version = extract_version_from_filename(file_path.name)
        if version is not None:
            if version in migration_scripts:
                raise ValueError(
                    f"Duplicate migration version {version}: "
                    f"{migration_scripts[version]} and {file_path}"
                )
            migration_scripts[version] = file_path
    return migration_scripts


def execute_sql_script(db_path: Path, script_path: Path) -> bool:
    """Execute a SQL script against the database.
    
    Args:
        db_path: Path to the SQLite database file
        script_path: Path to the SQL script file
        
    Returns:
        bool: True if the script executed successfully, False otherwise
    """
    db_path = Path(db_path)
    script_path = Path(script_path)
    # Connect directly to the database
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        
        # Read script content
        script_content = script_path.read_text()
        
        # Execute the script
        conn.executescript(script_content)
        return True
        
    except sqlite3.Error as e:
        # SQL error occurred
        print(f"Error executing SQL script {script_path}:", file=stderr)
        print(f"  {e}", file=stderr)
        return False
    
    except Exception as e:
        # Handle other errors (file not found, etc.)
        print(f"Error executing SQL script {script_path}:", file=stderr)
        print(f"  {e}", file=stderr)
        return False
        
    finally:
        if conn:
            conn.close()


def execute_python_script(db_path: Path, script_path: Path) -> bool:
    """Execute a Python script."""
    db_path = Path(db_path)
    script_path = Path(script_path)    
    try:
        subprocess.run(
            [sys.executable, script_path, db_path],
            capture_output=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing Python script {script_path}:", file=stderr)
        sys.stderr.write(e.stderr.decode())
        print("",file=stderr)
        return False


def execute_shell_script(db_path: Path, script_path: Path) -> bool:
    """Execute a shell script."""
    db_path = Path(db_path)
    script_path = Path(script_path)    
    try:
        subprocess.run(
            ["sh", script_path, db_path],
            capture_output=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing shell script {script_path}:", file=stderr)
        sys.stderr.write(e.stderr.decode())
        print("",file=stderr)
        return False


def create_db_backup(db_path: Path) -> Path | None:
    """Create a backup of the db, or returns None on failure.

    Uses the '.backup' SQLite command which ensures a consistent backup even if the
    database is in the middle of a transaction.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        Path: Path to the backup file, or None if the backup failed.
    """
    db_path = Path(db_path)
    # Only proceed if the database exists
    if not db_path.exists():
        print(f"Warning: Database file does not exist: {db_path}")
        return None

    # Create a timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(f"{db_path}.{timestamp}.backup")

    # Check if the backup file already exists
    if backup_path.exists():
        print(f"Error: Backup file already exists: {backup_path}", file=stderr)
        return None

    conn = None
    backup_conn = None
    try:
        # Connect to the databases
        conn = sqlite3.connect(db_path)
        backup_conn = sqlite3.connect(backup_path)

        # Perform the backup
        with backup_conn:
            conn.backup(backup_conn)

        if not backup_path.exists():
            raise Exception("Backup file was not created")

        print(f"Database backup created: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"Error during backup: {e}")
        # Attempt to remove potentially incomplete backup file
        if backup_path.exists():
            try:
                backup_path.unlink() # remove the file
                print(f"Removed incomplete backup file: {backup_path}")
            except OSError as remove_err:
                print(f"Error removing incomplete backup file: {remove_err}", file=stderr)
        return None
    finally:
        # this runs before return `backup_path` or `return None` in the try block
        if conn:
            conn.close()
        if backup_conn:
            backup_conn.close()


def create_database_backup(db_path:Path) -> Path | None:
    "See create_database_backup"
    warnings.warn("create_database_backup is deprecated, as it has been renamed to create_db_backup, which is functionally identical",
                 DeprecationWarning,
                  stacklevel=2)
    return create_db_backup(db_path)


def execute_migration_script(db_path: Path, script_path: Path) -> bool:
    """Execute a migration script based on its file extension."""
    db_path = Path(db_path)
    script_path = Path(script_path)    
    ext = os.path.splitext(script_path)[1].lower()
    
    if ext == ".sql":
        return execute_sql_script(db_path, script_path)
    elif ext == ".py":
        return execute_python_script(db_path, script_path)
    elif ext == ".sh":
        return execute_shell_script(db_path, script_path)
    else:
        print(f"Unsupported script type: {script_path}", file=stderr)
        return False


def run_migrations(
    db_path: Path, 
    migrations_dir: Path,
    verbose: bool = False
) -> bool:
    """Run all pending migrations.
    
    Args:
        db_path: Path to the SQLite database file
        migrations_dir: Path to the directory containing migration scripts
        verbose: If True, print detailed progress messages (False by default)

    Precondition:
    - DB must exist
    - DB must be versioned
    
    Returns True if all migrations succeed, False otherwise.
    """
    db_path = Path(db_path)
    migrations_dir = Path(migrations_dir)   
    # Keep track of migration statistics
    stats = {
        "applied": 0,
        "failed": 0
    }
    
    # Check if database file exists
    if not db_path.exists():
        print(f"Error: Database file does not exist: {db_path}", file=stderr)
        print("The database file must exist before running migrations.",file=stderr)
        return False
    
    try:
        # Ensure this is a managed db
        try:
            create_db(db_path)
        except sqlite3.Error as e:
            print(f"""Error: Cannot migrate the db at {db_path}.

This is because it is not managed by fastmigrate. Please do one of the following:

1. Create a new, managed db using `fastmigrate.create_db()` or
`fastmigrate_create_db`
            
2. Enroll your existing database, as described in
https://answerdotai.github.io/fastmigrate/enrolling.html""",file=stderr)
            return False
        
        # Get current version
        current_version = get_db_version(db_path)
        
        # Get all migration scripts
        try:
            migration_scripts = get_migration_scripts(migrations_dir)
        except ValueError as e:
            print(f"Error: {e}", file=stderr)
            return False
        
        # Find pending migrations
        pending_migrations = {
            version: path
            for version, path in migration_scripts.items()
            if version > current_version
        }
        
        if not pending_migrations:
            if verbose:
                print(f"Database is up to date (version {current_version})")
            return True
        
        # Sort migrations by version
        sorted_versions = sorted(pending_migrations.keys())
            
        # Execute migrations
        for version in sorted_versions:
            script_path = pending_migrations[version]
            script_name = script_path.name
            
            if verbose:
                print(f"Applying migration {version}: {script_name}")
            
            # Each script will open its own connection
            
            # Execute the migration script
            success = execute_migration_script(db_path, script_path)
            
            if not success:
                # Show summary of failure - always show errors regardless of verbose flag
                stats["failed"] += 1
                print(f"""Migration failed: {script_path}
  • {stats['applied']} migrations applied
  • {stats['failed']} migrations failed""", file=stderr)
                
                return False
            
            stats["applied"] += 1
            
            # Update version
            _set_db_version(db_path, version)
            if verbose:
                print(f"✓ Database updated to version {version}")
        
        # Show summary of successful run
        if stats["applied"] > 0 and verbose:
            print("\nMigration Complete")
            print(f"  • {stats['applied']} migrations applied")
            print(f"  • Database now at version {sorted_versions[-1]}")
        
        return True
    
    except sqlite3.Error as e:
        print(f"Database error: {e}", file=stderr)
        return False
    except Exception as e:
        print(f"Error: {e}", file=stderr)
        return False

def get_db_schema(db_path: Path) -> str:
    """Get the SQL schema of a SQLite database file.
    
    This function retrieves the CREATE statements for all tables, 
    indices, triggers, and views in the database.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        str: The SQL schema as a string
        
    Raises:
        FileNotFoundError: If database file doesn't exist
        sqlite3.Error: If unable to access the database
    """

    if not Path(db_path).exists(): raise FileNotFoundError(f"Database does not exist: {db_path}")
    conn = Connection(str(db_path))
    out = StringIO()
    shell = Shell(stdout=out, db=conn)
    shell.process_command('.schema')
    sql = out.getvalue()
    if 'CREATE TABLE' in sql: sql = sql.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS")
    if 'CREATE INDEX' in sql: sql = sql.replace("CREATE INDEX", "CREATE INDEX IF NOT EXISTS")    
    return sql