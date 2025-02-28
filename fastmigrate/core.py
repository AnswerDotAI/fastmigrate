"""Core functionality for fastmigrate."""

import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from rich.console import Console

# Initialize Rich console
console = Console()


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
        # Table doesn't exist, create it with version 0
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
        console.print(f"[bold red]Error[/bold red] executing SQL script {script_path}:")
        console.print(f"  {e}", style="red")
        return False
    
    except Exception as e:
        # Handle other errors (file not found, etc.)
        console.print(f"[bold red]Error[/bold red] executing SQL script {script_path}:")
        console.print(f"  {e}", style="red")
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
        console.print(f"[bold red]Error[/bold red] executing Python script {script_path}:")
        console.print(e.stderr.decode(), style="red")
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
        console.print(f"[bold red]Error[/bold red] executing shell script {script_path}:")
        console.print(e.stderr.decode(), style="red")
        return False


def create_database_backup(db_path: str) -> str:
    """Create a backup of the SQLite database file using SQLite's built-in backup command.
    
    Uses the '.backup' SQLite command which ensures a consistent backup even if the
    database is in the middle of a transaction.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        str: Path to the backup file
    """
    # Only proceed if the database exists
    if not os.path.exists(db_path):
        console.print(f"[yellow]Warning:[/yellow] Database file does not exist: {db_path}")
        return ""
        
    # Create a timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.{timestamp}.backup"
    
    # Create the backup using sqlite3 command line
    try:
        # Construct the command that will be executed
        sqlite_command = f"sqlite3 '{db_path}' \".backup '{backup_path}'\""
        console.print(f"Executing: {sqlite_command}")
        
        # Execute the SQLite backup command
        result = subprocess.run(
            sqlite_command,
            shell=True,
            capture_output=True,
            text=True
        )
        
        # Check for errors
        if result.returncode != 0:
            raise Exception(f"SQLite backup command failed: {result.stderr}")
        
        # Verify the backup file was created
        if not os.path.exists(backup_path):
            raise Exception("Backup file was not created")
            
        console.print(f"[green]Database backup created:[/green] {backup_path}")
        return backup_path
    except Exception as e:
        console.print(f"[bold red]Error creating backup:[/bold red] {e}")
        return ""


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
        console.print(f"[bold red]Unsupported script type:[/bold red] {script_path}")
        return False


def run_migrations(
    db_path: str, 
    migrations_dir: str
) -> bool:
    """Run all pending migrations.
    
    Args:
        db_path: Path to the SQLite database file
        migrations_dir: Path to the directory containing migration scripts
    
    Returns True if all migrations succeed, False otherwise.
    """
    # Keep track of migration statistics
    stats = {
        "applied": 0,
        "failed": 0,
        "total_time": 0
    }
    
    # Check if database file exists
    if not os.path.exists(db_path):
        console.print(f"[bold red]Error:[/bold red] Database file does not exist: {db_path}")
        console.print("The database file must exist before running migrations.")
        return False
    
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
            console.print(f"[bold red]Error:[/bold red] {e}")
            return False
        
        # Find pending migrations
        pending_migrations = {
            version: path
            for version, path in migration_scripts.items()
            if version > current_version
        }
        
        if not pending_migrations:
            console.print(f"[green]Database is up to date[/green] (version {current_version})")
            return True
        
        # Sort migrations by version
        sorted_versions = sorted(pending_migrations.keys())
            
        # Execute migrations
        start_time = time.time()
        for version in sorted_versions:
            script_path = pending_migrations[version]
            script_name = os.path.basename(script_path)
            
            # Start timing this migration
            migration_start = time.time()
            console.print(f"[blue]Applying[/blue] migration [bold]{version}[/bold]: [cyan]{script_name}[/cyan]")
            
            # Close the connection before running the script
            # Each script will open its own connection
            conn.close()
            conn = None
            
            # Execute the migration script
            success = execute_migration_script(db_path, script_path)
            
            if not success:
                console.print(f"[bold red]Migration failed:[/bold red] {script_path}")
                stats["failed"] += 1
                
                # Show summary
                console.print("\n[bold red]Migration Failed[/bold red]")
                console.print(f"  • [bold]{stats['applied']}[/bold] migrations applied")
                console.print(f"  • [bold]{stats['failed']}[/bold] migrations failed")
                console.print(f"  • Total time: [bold]{time.time() - start_time:.2f}[/bold] seconds")
                
                return False
            
            # Record migration duration
            migration_duration = time.time() - migration_start
            stats["total_time"] += migration_duration
            stats["applied"] += 1
            
            # Reopen connection and update version
            conn = sqlite3.connect(db_path)
            set_db_version(conn, version)
            console.print(f"[green]✓[/green] Database updated to version [bold]{version}[/bold] [dim]({migration_duration:.2f}s)[/dim]")
        
        # Show summary of successful run
        if stats["applied"] > 0:
            total_duration = time.time() - start_time
            console.print("\n[bold green]Migration Complete[/bold green]")
            console.print(f"  • [bold]{stats['applied']}[/bold] migrations applied")
            console.print(f"  • Database now at version [bold]{sorted_versions[-1]}[/bold]")
            console.print(f"  • Total time: [bold]{total_duration:.2f}[/bold] seconds")
        
        return True
    
    finally:
        if conn:
            conn.close()