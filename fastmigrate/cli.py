"""Command-line interface for fastmigrate."""

import os
import sys
from pathlib import Path
import sqlite3
from typing import Dict, Any

import typer
from typer import Typer
import configparser

from fastmigrate.core import run_migrations, create_db_backup, get_db_version, create_db as create_db_core

# Define constants - single source of truth for default values
DEFAULT_DB = Path("data/database.db")
DEFAULT_MIGRATIONS = Path("migrations")
DEFAULT_CONFIG = Path(".fastmigrate")

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

def _get_config(config_path: Path, db: Path|None=None, migrations: Path|None=None) -> tuple[Path|None]:        
    if config_path.exists():
        cfg = configparser.ConfigParser()
        cfg.read(config_path)
        if "paths" in cfg:
            # Only use config values if CLI values are defaults
            if "db" in cfg["paths"] and db == DEFAULT_DB:
                db_path = Path(cfg["paths"]["db"])
            else:
                db_path = db
            if "migrations" in cfg["paths"] and migrations == DEFAULT_MIGRATIONS:
                migrations_path = Path(cfg["paths"]["migrations"])
            else:
                migrations_path = migrations
    else:
        db_path = db
        migrations_path = migrations
    return db_path, migrations_path

@app.command()
def backup(
    db: Path = typer.Option(
        DEFAULT_DB, "--db", help="Path to the SQLite database file"
    ),
    config_path: Path = typer.Option(
        DEFAULT_CONFIG, "--config", help="Path to config file (default: .fastmigrate)"
    )
) -> None:
    """Create a backup of the SQLite database."""
    db_path, migrations_path = _get_config(config_path, db)
    if create_db_backup(db_path) is None:
        sys.exit(1)    

@app.command()
def create_db(
    db: Path = typer.Option(
        DEFAULT_DB, "--db", help="Path to the SQLite database file"
    ),
    config_path: Path = typer.Option(
        DEFAULT_CONFIG, "--config", help="Path to config file (default: .fastmigrate)"
    )
) -> None:
    """Create a new SQLite database, with versioning build-in.
        Existing databases will not be modified."""
    db_path, migrations_path = _get_config(config_path, db)
    print(f"Creating database at {db_path}")
    try:
        # Check if file existed before we call create_db
        file_existed_before = db_path.exists()
    
        version = create_db_core(db_path)
    
        if not db_path.exists():
            typer.echo(f"Error: Expected database file to be created at {db_path}")
            sys.exit(1)
    
        if not file_existed_before:
            typer.echo(f"Created new versioned SQLite database with version=0 at: {db_path}")
        else:
            typer.echo(f"A versioned database (version: {version}) already exists at: {db_path}")
    
        sys.exit(0)
    except sqlite3.Error as e:
        typer.echo(f"An unversioned db already exists at {db_path}, or there was some other write error.\nError: {e}")
        sys.exit(1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        sys.exit(1)    

@app.command()
def migrate(
    db: Path = typer.Option(
        DEFAULT_DB, "--db", help="Path to the SQLite database file"
    ),
    migrations: Path = typer.Option(
        DEFAULT_MIGRATIONS, "--migrations", help="Path to the migrations directory", 
        dir_okay=True, file_okay=False
    ),
    config_path: Path = typer.Option(
        DEFAULT_CONFIG, "--config", help="Path to config file (default: .fastmigrate)"
    )
) -> None:
    """Run SQLite database migrations."""
    db_path, migrations_path = _get_config(config_path, db, migrations)
    success = run_migrations(db_path, migrations_path, verbose=True)    
    if not success:
        sys.exit(1)

@app.command()
def version(
    db: Path = typer.Option(
        DEFAULT_DB, "--db", help="Path to the SQLite database file"
    ),
    config_path: Path = typer.Option(
        DEFAULT_CONFIG, "--config", help="Path to config file (default: .fastmigrate)"
    )
) -> None:
    """Show the version of fastmigrate and the SQLite database."""
    typer.echo(f"FastMigrate version: {VERSION}")    
    db_path, _ = _get_config(config_path, db)
    if db_path is None:
        typer.echo("No database file specified.")
        sys.exit(1)
    if not db_path.exists():
        typer.echo(f"Database file does not exist: {db_path}")
        sys.exit(1)
    try:
        db_version = get_db_version(db_path)
        typer.echo(f"Database version: {db_version}")
    except sqlite3.Error:
        typer.echo("Database is unversioned (no _meta table)")
    return   


if __name__ == "__main__":
    app()
