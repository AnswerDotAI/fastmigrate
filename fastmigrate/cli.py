"""Command-line interface for fastmigrate."""

import os
import sys
from pathlib import Path
from typing import Optional

import typer
import configparser

from fastmigrate.core import run_migrations

app = typer.Typer(help="Structured migration of data in SQLite databases")


@app.command()
def main(
    db: str = typer.Option(
        "data/database.db", "--db", help="Path to the SQLite database file"
    ),
    migrations: str = typer.Option(
        "migrations", "--migrations", help="Path to the migrations directory", 
        dir_okay=True, file_okay=False
    ),
    config: Path = typer.Option(
        ".fastmigrate", help="Path to config file (default: .fastmigrate)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show which migrations would be run without executing them"
    ),
    interactive: bool = typer.Option(
        False, "--interactive", help="Prompt for confirmation before each migration"
    ),
) -> None:
    """Run SQLite database migrations.
    
    Paths can be provided via CLI options or read from config file.
    """
    db_path = db
    migrations_path = migrations
    
    # Read from config file if it exists
    if config.exists():
        cfg = configparser.ConfigParser()
        cfg.read(config)
        if "paths" in cfg:
            # Config file overrides defaults, but CLI options override config file
            if "db" in cfg["paths"] and db == "data/database.db":  # Only if default wasn't overridden by CLI
                db_path = cfg["paths"]["db"]
            if "migrations" in cfg["paths"] and migrations == "migrations":  # Only if default wasn't overridden by CLI
                migrations_path = cfg["paths"]["migrations"]
    
    # Ensure db directory exists
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    
    # Run migrations
    success = run_migrations(db_path, migrations_path, dry_run=dry_run, interactive=interactive)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    app()