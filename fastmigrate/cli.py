"""Command-line interface for fastmigrate."""

import os
import sys
from pathlib import Path
from typing import Optional

import typer
from typer import Typer
import configparser

from fastmigrate.core import run_migrations

# Create a global app instance for testing
app = Typer(
    help="Structured migration of data in SQLite databases",
    context_settings={"help_option_names": ["-h", "--help"]}
)


def main_wrapper():
    """Entry point for the CLI."""
    # Create a new Typer app for the actual CLI (instead of using the global one for testing)
    # This keeps the CLI clean with just one command
    cli_app = Typer(
        help="Structured migration of data in SQLite databases",
        context_settings={"help_option_names": ["-h", "--help"]}
    )
    
    # Get the version number
    try:
        from importlib.metadata import version as get_version
        version_string = get_version("fastmigrate")
    except ImportError:
        # Fallback for Python < 3.8
        try:
            import pkg_resources
            version_string = pkg_resources.get_distribution("fastmigrate").version
        except:
            version_string = "unknown"
    
    @cli_app.callback(invoke_without_command=True)
    def callback(
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
        version: bool = typer.Option(
            False, "--version", "-v", help="Show version and exit"
        ),
    ) -> None:
        """Run SQLite database migrations."""
        # Handle version flag
        if version:
            typer.echo(f"FastMigrate version: {version_string}")
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
        
        # Ensure db directory exists
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        
        # Run migrations
        success = run_migrations(db_path, migrations_path, dry_run=dry_run, interactive=interactive)
        if not success:
            sys.exit(1)
    
    # Run the app
    cli_app()


# Add a command to the global app instance for testing
@app.command()
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
) -> None:
    """Run SQLite database migrations.
    
    Paths can be provided via CLI options or read from config file.
    """
    # This is a stub implementation used for testing
    # The actual implementation is in main_wrapper
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
    
    # Ensure db directory exists
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    
    # Run migrations
    success = run_migrations(db_path, migrations_path, dry_run=dry_run, interactive=interactive)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main_wrapper()