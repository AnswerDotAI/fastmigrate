"""fastmigrate - Structured migration of data in SQLite databases."""

__version__ = "0.3.0"

from fastmigrate.core import run_migrations, create_db, ensure_versioned_db, get_db_version, create_db_backup, create_database_backup
from fastmigrate.migrations import recreate_table

__all__ = ["run_migrations", "create_db", "get_db_version", "create_db_backup", "recreate_table",
           # deprecated
           "ensure_versioned_db",
           "create_database_backup"]

