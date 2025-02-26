"""Command-line interface for fastmigrate."""

import os
import sys
from pathlib import Path
from typing import Optional

import typer
from typer import Typer
import configparser
from rich.console import Console

from fastmigrate.core import run_migrations

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

# Define a shared function that contains the core migration logic
def run_cli_migration(
    db: str, 
    migrations: str, 
    config_path: str,
    dry_run: bool,
    interactive: bool,
    show_version: bool = False,
    create_db: bool = False
) -> None:
    """Run the migration process with CLI parameters."""
    # Handle version flag
    if show_version:
        typer.echo(f"FastMigrate version: {VERSION}")
        return
        
    db_path = db
    migrations_path = migrations
    
    # Read from config file if it exists
    config_file = Path(config_path)
    if config_file.exists():
        cfg = configparser.ConfigParser()
        cfg.read(config_file)
        if "paths" in cfg:
            # Config file overrides defaults, but CLI options override config file
            if "db" in cfg["paths"] and db == "data/database.db":  # Only if default wasn't overridden by CLI
                db_path = cfg["paths"]["db"]
            if "migrations" in cfg["paths"] and migrations == "migrations":  # Only if default wasn't overridden by CLI
                migrations_path = cfg["paths"]["migrations"]
    
    # Create parent directory
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    
    # Create database file if requested and it doesn't exist
    if create_db and not os.path.exists(db_path):
        # Create an empty SQLite database
        conn = sqlite3.connect(db_path)
        conn.close()
        typer.echo(f"Created new SQLite database at: {db_path}")
    
    # Run migrations
    success = run_migrations(db_path, migrations_path, dry_run=dry_run, interactive=interactive)
    if not success:
        sys.exit(1)

# This command can be used by tests and is also exposed via CLI
@app.callback(invoke_without_command=True)
def main(
    db: str = typer.Option(
        "data/database.db", "--db", help="Path to the SQLite database file"
    ),
    migrations: str = typer.Option(
        "migrations", "--migrations", help="Path to the migrations directory", 
        dir_okay=True, file_okay=False
    ),
    config_path: str = typer.Option(
        ".fastmigrate", "--config", help="Path to config file (default: .fastmigrate)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show which migrations would be run without executing them"
    ),
    interactive: bool = typer.Option(
        False, "--interactive", help="Prompt for confirmation before each migration"
    ),
    create_db: bool = typer.Option(
        False, "--createdb", help="Create the database file if it doesn't exist"
    ),
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version and exit"
    ),
) -> None:
    """Run SQLite database migrations.
    
    Paths can be provided via CLI options or read from config file.
    """
    run_cli_migration(db, migrations, config_path, dry_run, interactive, version, create_db)

# This function is our CLI entry point (called when the user runs 'fastmigrate')
def main_wrapper():
    """Entry point for the CLI."""
    # Simply use the app we've already defined above
    app()

if __name__ == "__main__":
    main_wrapper()