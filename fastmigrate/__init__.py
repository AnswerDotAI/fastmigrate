"fastmigrate - Structured migration of data in SQLite databases."
__version__ = "0.5.1"

from fastmigrate.core import ( run_migrations, setup_logging, create_db, ensure_versioned_db, get_db_version, create_db_backup, create_database_backup,)

# Optional: recreate_table depends on apswutils, which is not required for the
# core migration runner.
try: from fastmigrate.migrations import recreate_table
except Exception:  # pragma: no cover
    def recreate_table(*args, **kwargs):  # type: ignore
        raise ImportError( "fastmigrate.recreate_table requires the optional 'apswutils' dependency")

__all__ = ["run_migrations", "setup_logging", "create_db", "get_db_version", "create_db_backup", "recreate_table",
           "ensure_versioned_db", "create_database_backup"]
