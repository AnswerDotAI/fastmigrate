"""fastmigrate - Structured migration of data in SQLite databases."""

__version__ = "0.2.2"

from fastmigrate.core import run_migrations, ensure_versioned_db, ensure_meta_table, get_db_version, set_db_version, create_database_backup

__all__ = ["run_migrations", "ensure_versioned_db", "ensure_meta_table", "get_db_version", "set_db_version", "create_database_backup"]
