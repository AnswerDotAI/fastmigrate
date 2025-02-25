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
    db: Optional[Path] = typer.Option(
        None, help="Path to the SQLite database file"
    ),
    migrations: Optional[Path] = typer.Option(
        None, help="Path to the migrations directory", dir_okay=True, file_okay=False
    ),
    config: Path = typer.Option(
        ".fastmigrate", help="Path to config file (default: .fastmigrate)"
    ),
) -> None:
    """Run SQLite database migrations.
    
    If not provided via CLI options, paths will be read from config file
    or use the default values.
    """
    # Config defaults
    db_path = "data/database.db"
    migrations_path = "migrations"
    
    # Read from config file if it exists
    if config.exists():
        cfg = configparser.ConfigParser()
        cfg.read(config)
        if "paths" in cfg:
            if "db" in cfg["paths"] and not db:
                db_path = cfg["paths"]["db"]
            if "migrations" in cfg["paths"] and not migrations:
                migrations_path = cfg["paths"]["migrations"]
    
    # Command-line options override config file
    if db:
        db_path = str(db)
    if migrations:
        migrations_path = str(migrations)
    
    # Ensure db directory exists
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    
    # Run migrations
    success = run_migrations(db_path, migrations_path)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    app()