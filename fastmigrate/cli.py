"""Command-line interface for fastmigrate."""

import os
import sys
from pathlib import Path
import sqlite3
from typing import Dict, Any

import typer
from typer import Typer
import configparser

from fastmigrate.core import run_migrations, create_database_backup, get_db_version

# Define constants - single source of truth for default values
DEFAULT_DB = "data/database.db"
DEFAULT_MIGRATIONS = "migrations"
DEFAULT_CONFIG = ".fastmigrate"

# Get the version number
try:
    from importlib.metadata import version as get_version
    VERSION = get_version("fastmigrate")
except ImportError:
    # Fallback for Python < 3.8
    try:
        import pkg_resources
        VERSION = pkg_resources.get_distribution("fastmigrate").version
    except:
        VERSION = "unknown"

# Create a global app instance used by both tests and CLI
app = Typer(
    help="Structured migration of data in SQLite databases",
    context_settings={"help_option_names": ["-h", "--help"]}
)

# This command can be used by tests and is also exposed via CLI
@app.callback(invoke_without_command=True)
def main(
    db: str = typer.Option(
        DEFAULT_DB, "--db", help="Path to the SQLite database file"
    ),
    migrations: str = typer.Option(
        DEFAULT_MIGRATIONS, "--migrations", help="Path to the migrations directory", 
        dir_okay=True, file_okay=False
    ),
    config_path: str = typer.Option(
        DEFAULT_CONFIG, "--config", help="Path to config file (default: .fastmigrate)"
    ),
    create_db: bool = typer.Option(
        False, "--createdb", help="Create the database file if it doesn't exist. Don't run migrations."
    ),
    backup: bool = typer.Option(
        False, "--backup", help="Create a timestamped backup of the database before running migrations"
    ),
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version and exit"
    ),
    check_db_version: bool = typer.Option(
        False, "--check_db_version", help="Check the database version and exit"
    ),
) -> None:
    """Run SQLite database migrations.
    
    FastMigrate applies migration scripts to a SQLite database in sequential order.
    It keeps track of which migrations have been applied using a _meta table
    in the database, and only runs scripts that have not yet been applied.
    
    Paths can be provided via CLI options or config file, with CLI options taking precedence.
    """
    # Handle version flag first
    if version:
        typer.echo(f"FastMigrate version: {VERSION}")
        return
        
    # Handle check_db_version flag
    if check_db_version:
        if not os.path.exists(db):
            typer.echo(f"Database file does not exist: {db}")
            sys.exit(1)
        try:
            db_version = get_db_version(db)
            typer.echo(f"Database version: {db_version}")
        except sqlite3.Error:
            typer.echo("Database is unversioned (no _meta table)")
        return
    
    # Read config file paths (if config file exists)
    config_file = Path(config_path)
    db_path = db
    migrations_path = migrations
    
    # Apply config file settings only if CLI values are defaults
    if config_file.exists():
        cfg = configparser.ConfigParser()
        cfg.read(config_file)
        if "paths" in cfg:
            # Only use config values if CLI values are defaults
            if "db" in cfg["paths"] and db == DEFAULT_DB:
                db_path = cfg["paths"]["db"]
            if "migrations" in cfg["paths"] and migrations == DEFAULT_MIGRATIONS:
                migrations_path = cfg["paths"]["migrations"]
    
    # Create parent directory
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    
    # Create database file if requested and it doesn't exist
    if create_db and not os.path.exists(db_path):
        # Create an empty file
        sqlite3.connect(db_path).close()
        
        # Initialize the meta table
        try:
            from fastmigrate.core import ensure_meta_table
            ensure_meta_table(db_path)
            typer.echo(f"Created new SQLite database with _meta table at: {db_path}")
            sys.exit(0)
        except sqlite3.Error as e:
            typer.echo(f"Error creating database: {e}")
            sys.exit(1)
    
    # Create a backup if requested
    if backup and os.path.exists(db_path):
        create_database_backup(db_path)
    
    # Run migrations with verbose=True for CLI usage
    success = run_migrations(db_path, migrations_path, verbose=True)
    if not success:
        sys.exit(1)

# This function is our CLI entry point (called when the user runs 'fastmigrate')
def main_wrapper() -> None:
    """Entry point for the CLI."""
    # Simply use the app we've already defined above
    app()

if __name__ == "__main__":
    main_wrapper()
