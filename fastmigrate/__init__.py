"""fastmigrate - Structured migration of data in SQLite databases."""

__version__ = "0.2.3"

from fastmigrate.core import run_migrations, ensure_versioned_db, ensure_meta_table, get_db_version, set_db_version, create_database_backup

from fastmigrate.migrations import recreate_table

__all__ = ["run_migrations", "ensure_versioned_db", "ensure_meta_table", "get_db_version", "set_db_version", "create_database_backup", "recreate_table"]
