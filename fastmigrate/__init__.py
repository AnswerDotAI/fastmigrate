"""fastmigrate - Check SQLite database versions and run structured migrations."""

__version__ = "0.2.4"

from fastmigrate.core import run_migrations, create_db, ensure_versioned_db, get_db_version, create_database_backup
from fastmigrate.migrations import recreate_table

__all__ = ["run_migrations", "create_db", "get_db_version", "create_database_backup", "recreate_table",
           # deprecated
           "ensure_versioned_db"]

