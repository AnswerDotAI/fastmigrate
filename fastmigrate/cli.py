"""Command-line interface for fastmigrate."""

import os
import sys
from pathlib import Path
import sqlite3
from fastcore.script import call_parse # type:ignore
import configparser
from importlib.metadata import version

from fastmigrate import core

# Define constants - single source of truth for default values
DEFAULT_DB = Path("data/database.db")
DEFAULT_MIGRATIONS = Path("migrations")
DEFAULT_CONFIG = Path(".fastmigrate")

def _get_config(
        config_path: Path,     # config file, which may not exist
        db: Path,              # db file, which need not exist
        migrations: Path=DEFAULT_MIGRATIONS # migrations dir, which may not exist
    ) -> tuple[Path, Path]:
    """Performs final value resolution for db and migrations.

    CLI args > config file > default values.

    This function's arguments are values for db and migrations, which
    are either from the CLI or else are the default values to use when
    no value is supplied at the CLI nor by a config file.

    If a config file exists, and the argument values are the default
    values, then we _assume_ the argument values come from the
    defaults, and then the config file values are used.

    (Consequently, there is no way for the user to explicitly specify
    a value which is equal to the default value, and to have that take
    precedence over a conflicting value in the config file!)
    """
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

@call_parse
def backup_db(
    db: Path = DEFAULT_DB, # Path to the SQLite database file
    config_path: Path = DEFAULT_CONFIG # Path to config file
) -> None:
    """Create a backup of the SQLite database.

    Note: command line arguments take precedence over values from a
    config file, unless they are equal to default values.
    """
    db_path, _ = _get_config(config_path, db)
    if core.create_db_backup(db_path) is None:
        sys.exit(1) 

@call_parse
def check_version(
    db: Path = DEFAULT_DB, # Path to the SQLite database file
    config_path: Path = DEFAULT_CONFIG # Path to config file
) -> None:
    """Show the version of fastmigrate and the SQLite database.

    Note: command line arguments take precedence over values from a
    config file, unless they are equal to default values.
    """
    print(f"FastMigrate version: {version('fastmigrate')}")    
    db_path, _ = _get_config(config_path, db)
    if not db_path.exists():
        print(f"Database file does not exist: {db_path}")
        sys.exit(1)
    try:
        db_version = core.get_db_version(db_path)
        print(f"Database version: {db_version}")
    except sqlite3.Error:
        print("Database is unversioned (no _meta table)")
    return   


@call_parse
def create_db(
        db: Path = DEFAULT_DB, # Path to SQLite db file, which may not exist
        config_path: Path = DEFAULT_CONFIG # Path to config file
) -> None:
    """Create a new SQLite database, with versioning build-in.

    Existing databases will never be modified.

    Note: command line arguments take precedence over values from a
    config file, unless they are equal to default values.
    """
    db_path, _ = _get_config(config_path, db)
    print(f"Creating database at {db_path}")
    try:
        # Check if file existed before we call create_db
        file_existed_before = db_path.exists()
    
        version = core.create_db(db_path)
    
        if not db_path.exists():
            print(f"Error: Expected database file to be created at {db_path}")
            sys.exit(1)
    
        if not file_existed_before:
            print(f"Created new versioned SQLite database with version=0 at: {db_path}")
        else:
            print(f"A versioned database (version: {version}) already exists at: {db_path}")
    
        sys.exit(0)
    except sqlite3.Error as e:
        print(f"An unversioned db already exists at {db_path}, or there was some other write error.\nError: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

@call_parse
def run_migrations(
    db: Path = DEFAULT_DB, # Path to the SQLite database file
    migrations: Path = DEFAULT_MIGRATIONS, # Path to the migrations directory
    config_path: Path = DEFAULT_CONFIG # Path to config file
) -> None:
    """Run SQLite database migrations.

    Note: command line arguments take precedence over values from a
    config file, unless they are equal to default values.
    """
    db_path, migrations_path = _get_config(config_path, db, migrations)
    success = core.run_migrations(db_path, migrations_path, verbose=True)    
    if not success:
        sys.exit(1)

