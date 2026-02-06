"""Core functionality for fastmigrate.

fastmigrate is SQLite-first by default. However, if a ``config.py`` file is
present at the root of a migrations directory, :func:`run_migrations` will use
it as a backend adapter to run migrations against *any* database.

The adapter API is intentionally tiny and does not assume DB-API, SQLAlchemy,
asyncpg, etc. Each adapter hook may be sync or async; if any hook returns an
awaitable, fastmigrate will automatically await it.
"""

import asyncio
import hashlib
import importlib.util
import inspect
import os
import re
import sqlite3
import subprocess
import sys
import threading
import warnings
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from sys import stderr
from types import ModuleType
from typing import Any, Awaitable, Callable, Dict, Optional



__all__ = ["run_migrations", "create_db", "get_db_version", "create_db_backup",
           # deprecated
           "ensure_versioned_db",
           "create_database_backup"]


@dataclass(frozen=True)
class _UserBackend:
    """Backend adapter loaded from ``migrations/config.py``."""

    module: ModuleType
    get_connection: Callable[[Any], Any]
    ensure_meta_table: Callable[[Any], Any]
    get_version: Callable[[Any], Any]
    set_version: Callable[[Any, int], Any]
    execute_sql: Callable[[Any, str], Any]
    close_connection: Optional[Callable[[Any], Any]] = None


def _load_user_backend(migrations_dir: Path) -> Optional[_UserBackend]:
    """Load a user backend adapter from ``migrations_dir/config.py`` if present."""
    migrations_dir = Path(migrations_dir)
    config_path = migrations_dir / "config.py"
    if not config_path.exists():
        return None

    # Use a stable-ish but unique module name to avoid collisions when tests
    # create multiple temporary migration dirs.
    digest = hashlib.sha256(str(config_path).encode("utf-8")).hexdigest()[:12]
    module_name = f"fastmigrate_user_config_{digest}"

    spec = importlib.util.spec_from_file_location(module_name, config_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to import config.py from {config_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[call-arg]

    required = [
        "get_connection",
        "ensure_meta_table",
        "get_version",
        "set_version",
        "execute_sql",
    ]
    missing = [name for name in required if not hasattr(module, name)]
    if missing:
        raise AttributeError(
            f"config.py is missing required function(s): {', '.join(missing)}"
        )

    backend = _UserBackend(
        module=module,
        get_connection=getattr(module, "get_connection"),
        ensure_meta_table=getattr(module, "ensure_meta_table"),
        get_version=getattr(module, "get_version"),
        set_version=getattr(module, "set_version"),
        execute_sql=getattr(module, "execute_sql"),
        close_connection=getattr(module, "close_connection", None),
    )

    # Basic validation: required hooks must be callable.
    for name in required:
        if not callable(getattr(backend, name)):
            raise TypeError(f"config.py function '{name}' is not callable")
    if backend.close_connection is not None and not callable(backend.close_connection):
        raise TypeError("config.py function 'close_connection' is not callable")

    return backend


async def _maybe_await(value: Any) -> Any:
    """Await *value* if it is awaitable, otherwise return it unchanged."""
    if inspect.isawaitable(value):
        return await value
    return value


def _run_async_blocking(coro: Awaitable[Any]) -> Any:
    """Run an async coroutine from sync code.

    If we're already inside an event loop, run the coroutine in a dedicated
    thread to avoid "asyncio.run() cannot be called from a running event loop".
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # Running loop detected.
    result_box: dict[str, Any] = {}
    err_box: dict[str, BaseException] = {}

    def _runner() -> None:
        try:
            result_box["result"] = asyncio.run(coro)
        except BaseException as e:  # pragma: no cover - hard to trigger reliably
            err_box["err"] = e

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join()
    if "err" in err_box:
        raise err_box["err"]
    return result_box.get("result")

def create_db(db_path:Path) -> int:
    """Creates a versioned db, or ensures the existing db is versioned.

    If no db exists, creates an EMPTY db with version 0. (This is ready
    to be initalized by migration script with version 1.)

    If a db exists, which already has a version, does nothing.

    If a db exists, without a version, raises an sqlite3.Error
    """
    db_path = Path(db_path)
    if not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.close()
        _ensure_meta_table(db_path)
        return 0
    else:
        return get_db_version(db_path)


def ensure_versioned_db(db_path:Path) -> int:
    "See create_db"
    warnings.warn("ensure_versioned_db is deprecated, as it has been renamed to create_db, which is functionally identical",
                 DeprecationWarning,
                  stacklevel=2)
    return create_db(db_path)

def _ensure_meta_table(db_path: Path) -> None:
    """Create the _meta table if it doesn't exist, with a single row constraint.

    Uses a single-row pattern with a PRIMARY KEY on a constant value (1).
    This ensures we can only have one row in the table.

    WARNING: users should call this directly only if preparing a
    versioned db manually, for instance, for testing or for enrolling
    a non-version db after verifying its values and schema are what
    would be produced by migration scripts.

    Args:
        db_path: Path to the SQLite database

    Raises:
        FileNotFoundError: If database file doesn't exist
        sqlite3.Error: If unable to read or write to the database

    """
    db_path = Path(db_path)
    # First check if the file exists
    if not db_path.exists():
        raise FileNotFoundError(f"Database file does not exist: {db_path}")

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        # Check if _meta table exists
        cursor = conn.execute(
            """
            SELECT name, sql FROM sqlite_master
            WHERE type='table' AND name='_meta'
            """
        )
        row = cursor.fetchone()

        if row is None:
            # Table doesn't exist, create it with version 0
            try:
                with conn:
                    conn.execute(
                        """
                        CREATE TABLE _meta (
                            id INTEGER PRIMARY KEY CHECK (id = 1),
                            version INTEGER NOT NULL DEFAULT 0
                        )
                        """
                    )
                    conn.execute("INSERT INTO _meta (id, version) VALUES (1, 0)")
            except sqlite3.Error as e: raise sqlite3.Error(f"Failed to create _meta table: {e}")
    except sqlite3.Error as e: raise sqlite3.Error(f"Failed to access database: {e}")
    finally:
        if conn: conn.close()


def get_db_version(db_path: Path) -> int:
    """Get the current database version.

    Args:
        db_path: Path to the SQLite database

    Returns:
        int: The current database version

    Raises:
        FileNotFoundError: If database file doesn't exist
        sqlite3.Error: If unable to read the db version because it is not managed
    """
    db_path = Path(db_path)
    # First check if the file exists
    if not db_path.exists():
        raise FileNotFoundError(f"Database file does not exist: {db_path}")

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version FROM _meta WHERE id = 1")
        result = cursor.fetchone()
        if result is None:
            raise sqlite3.Error("No version found in _meta table")
        return int(result[0])
    except sqlite3.OperationalError:
        raise sqlite3.Error("_meta table does not exist")
    except sqlite3.Error as e:
        raise sqlite3.Error(f"Failed to get database version: {e}")
    finally:
        if conn:
            conn.close()


def _set_db_version(db_path: Path, version: int) -> None:
    """Set the database version.

    Uses an UPSERT pattern (INSERT OR REPLACE) to ensure we always set the
    version for id=1, even if the row doesn't exist yet.

    Args:
        db_path: Path to the SQLite database
        version: The version number to set

    Raises:
        FileNotFoundError: If database file doesn't exist
        sqlite3.Error: If unable to write to the database
    """
    db_path = Path(db_path)
    # First check if the file exists
    if not db_path.exists():
        raise FileNotFoundError(f"Database file does not exist: {db_path}")

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO _meta (id, version)
                    VALUES (1, ?)
                    """,
                    (version,)
                )
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Failed to set version: {e}")
    except sqlite3.Error as e:
        raise sqlite3.Error(f"Failed to access database: {e}")
    finally:
        if conn:
            conn.close()


def extract_version_from_filename(filename: str) -> Optional[int]:
    """Extract the version number from a migration script filename."""
    filename = str(filename) # Force Path objects to string
    match = re.match(r"^(\d{4})-.*\.(py|sql|sh)$", filename)
    if match:
        return int(match.group(1))
    return None


def get_migration_scripts(migrations_dir: Path) -> Dict[int, Path]:
    """Get all valid migration scripts from the migrations directory.

    Returns a dictionary mapping version numbers to file paths.
    Raises ValueError if two scripts have the same version number.
    """
    migrations_dir = Path(migrations_dir)
    migration_scripts: Dict[int, Path] = {}
    if not migrations_dir.exists():
        return migration_scripts

    for file_path in [x for x in migrations_dir.iterdir() if x.is_file()]:
        version = extract_version_from_filename(file_path.name)
        if version is not None:
            if version in migration_scripts:
                raise ValueError(
                    f"Duplicate migration version {version}: "
                    f"{migration_scripts[version]} and {file_path}"
                )
            migration_scripts[version] = file_path
    return migration_scripts


def execute_sql_script(db_path: Path, script_path: Path) -> bool:
    """Execute a SQL script against the database.

    Args:
        db_path: Path to the SQLite database file
        script_path: Path to the SQL script file

    Returns:
        bool: True if the script executed successfully, False otherwise
    """
    db_path = Path(db_path)
    script_path = Path(script_path)
    # Connect directly to the database
    conn = None
    try:
        conn = sqlite3.connect(db_path)

        # Read script content
        script_content = script_path.read_text()

        # Execute the script
        conn.executescript(script_content)
        return True

    except sqlite3.Error as e:
        # SQL error occurred
        print(f"Error executing SQL script {script_path}:", file=stderr)
        print(f"  {e}", file=stderr)
        return False

    except Exception as e:
        # Handle other errors (file not found, etc.)
        print(f"Error executing SQL script {script_path}:", file=stderr)
        print(f"  {e}", file=stderr)
        return False

    finally:
        if conn:
            conn.close()


def execute_python_script(db: Any, script_path: Path) -> bool:
    """Execute a Python migration script.

    The script is invoked as: ``python <script_path> <db>``.

    ``db`` is passed through ``str(db)`` and may be a filesystem path, DSN,
    or any other identifier.
    """
    db_arg = str(db)
    script_path = Path(script_path)
    try:
        subprocess.run(
            [sys.executable, script_path, db_arg],
            capture_output=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing Python script {script_path}:", file=stderr)
        sys.stderr.write(e.stderr.decode())
        print("",file=stderr)
        return False


def execute_shell_script(db: Any, script_path: Path) -> bool:
    """Execute a shell migration script.

    The script is invoked as: ``sh <script_path> <db>``.

    ``db`` is passed through ``str(db)`` and may be a filesystem path, DSN,
    or any other identifier.
    """
    db_arg = str(db)
    script_path = Path(script_path)
    try:
        subprocess.run(
            ["sh", script_path, db_arg],
            capture_output=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing shell script {script_path}:", file=stderr)
        sys.stderr.write(e.stderr.decode())
        print("",file=stderr)
        return False


def create_db_backup(db_path: Path) -> Path | None:
    """Create a backup of the db, or returns None on failure.

    Uses the '.backup' SQLite command which ensures a consistent backup even if the
    database is in the middle of a transaction.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        Path: Path to the backup file, or None if the backup failed.
    """
    db_path = Path(db_path)
    # Only proceed if the database exists
    if not db_path.exists():
        print(f"Warning: Database file does not exist: {db_path}")
        return None

    # Create a timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(f"{db_path}.{timestamp}.backup")

    # Check if the backup file already exists
    if backup_path.exists():
        print(f"Error: Backup file already exists: {backup_path}", file=stderr)
        return None

    conn = None
    backup_conn = None
    try:
        # Connect to the databases
        conn = sqlite3.connect(db_path)
        backup_conn = sqlite3.connect(backup_path)

        # Perform the backup
        with backup_conn:
            conn.backup(backup_conn)

        if not backup_path.exists():
            raise Exception("Backup file was not created")

        print(f"Database backup created: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"Error during backup: {e}")
        # Attempt to remove potentially incomplete backup file
        if backup_path.exists():
            try:
                backup_path.unlink() # remove the file
                print(f"Removed incomplete backup file: {backup_path}")
            except OSError as remove_err:
                print(f"Error removing incomplete backup file: {remove_err}", file=stderr)
        return None
    finally:
        # this runs before return `backup_path` or `return None` in the try block
        if conn:
            conn.close()
        if backup_conn:
            backup_conn.close()


def create_database_backup(db_path:Path) -> Path | None:
    "See create_database_backup"
    warnings.warn("create_database_backup is deprecated, as it has been renamed to create_db_backup, which is functionally identical",
                 DeprecationWarning,
                  stacklevel=2)
    return create_db_backup(db_path)


def execute_migration_script(db_path: Path, script_path: Path) -> bool:
    """Execute a migration script based on its file extension."""
    db_path = Path(db_path)
    script_path = Path(script_path)
    ext = os.path.splitext(script_path)[1].lower()

    if ext == ".sql":
        return execute_sql_script(db_path, script_path)
    elif ext == ".py":
        return execute_python_script(db_path, script_path)
    elif ext == ".sh":
        return execute_shell_script(db_path, script_path)
    else:
        print(f"Unsupported script type: {script_path}", file=stderr)
        return False


async def _run_migrations_with_backend_async(
    db: Any,
    migrations_dir: Path,
    backend: _UserBackend,
    verbose: bool = False,
) -> bool:
    """Run migrations using a user-provided backend adapter.

    This supports both sync and async hooks. All hooks are executed within a
    single event loop to support async DB drivers that are loop-bound.
    """

    migrations_dir = Path(migrations_dir)

    # Keep track of migration statistics
    stats = {"applied": 0, "failed": 0}

    # Get all migration scripts
    try:
        migration_scripts = get_migration_scripts(migrations_dir)
    except ValueError as e:
        print(f"Error: {e}", file=stderr)
        return False

    # Acquire connection/handle (may be None, engine, pool, etc)
    conn = await _maybe_await(backend.get_connection(db))

    try:
        # Ensure _meta exists
        await _maybe_await(backend.ensure_meta_table(conn))

        # Current version
        current_version = int(await _maybe_await(backend.get_version(conn)))

        # Find pending migrations
        pending_migrations = {
            version: path
            for version, path in migration_scripts.items()
            if version > current_version
        }

        if not pending_migrations:
            if verbose:
                print(f"Database is up to date (version {current_version})")
            return True

        sorted_versions = sorted(pending_migrations.keys())

        for version in sorted_versions:
            script_path = Path(pending_migrations[version])
            script_name = script_path.name

            if verbose:
                print(f"Applying migration {version}: {script_name}")

            ext = os.path.splitext(script_name)[1].lower()
            success: bool

            if ext == ".sql":
                sql = script_path.read_text()
                result = await _maybe_await(backend.execute_sql(conn, sql))
                success = True if result is None else bool(result)
            elif ext == ".py":
                success = execute_python_script(db, script_path)
            elif ext == ".sh":
                success = execute_shell_script(db, script_path)
            else:
                print(f"Unsupported script type: {script_path}", file=stderr)
                success = False

            if not success:
                stats["failed"] += 1
                print(
                    f"""Migration failed: {script_path}
  • {stats['applied']} migrations applied
  • {stats['failed']} migrations failed""",
                    file=stderr,
                )
                return False

            stats["applied"] += 1

            # Update version
            await _maybe_await(backend.set_version(conn, int(version)))
            if verbose:
                print(f"✓ Database updated to version {version}")

        if stats["applied"] > 0 and verbose:
            print("\nMigration Complete")
            print(f"  • {stats['applied']} migrations applied")
            print(f"  • Database now at version {sorted_versions[-1]}")

        return True

    except Exception as e:
        print(f"Error: {e}", file=stderr)
        return False
    finally:
        if backend.close_connection is not None:
            try:
                await _maybe_await(backend.close_connection(conn))
            except Exception:
                # Best-effort cleanup; never mask migration errors.
                pass


def run_migrations(
    db_path: Any,
    migrations_dir: Path,
    verbose: bool = False
) -> bool:
    """Run all pending migrations.

    By default, fastmigrate operates on SQLite database files.

    If a ``config.py`` file exists in the root of ``migrations_dir``,
    fastmigrate will instead use that file as a backend adapter and will not
    assume the database is SQLite or that ``db_path`` is a filesystem path.

    Args:
        db_path: Database identifier (typically a SQLite db file path). If
            using a custom backend adapter, this can be anything (DSN string,
            engine, pool, etc) as long as your adapter understands it.
        migrations_dir: Path to the directory containing migration scripts.
        verbose: If True, print detailed progress messages.

    Returns True if all migrations succeed, False otherwise.
    """
    migrations_dir = Path(migrations_dir)
    if not migrations_dir.exists():
        print(f"Error: Migrations directory does not exist: {migrations_dir}", file=stderr)
        return False

    # Custom backend mode via migrations/config.py
    try:
        backend = _load_user_backend(migrations_dir)
    except Exception as e:
        print(f"Error loading migrations/config.py: {e}", file=stderr)
        return False
    if backend is not None:
        try:
            return bool(
                _run_async_blocking(
                    _run_migrations_with_backend_async(db_path, migrations_dir, backend, verbose)
                )
            )
        except Exception as e:
            print(f"Error: {e}", file=stderr)
            return False

    # SQLite-first default mode
    db_path = Path(db_path)
    # Keep track of migration statistics
    stats = {
        "applied": 0,
        "failed": 0
    }

    # Check if database file exists
    if not db_path.exists():
        print(f"Error: Database file does not exist: {db_path}", file=stderr)
        print("The database file must exist before running migrations.",file=stderr)
        return False

    try:
        # Ensure this is a managed db
        try:
            create_db(db_path)
        except sqlite3.Error as e:
            print(f"""Error: Cannot migrate the db at {db_path}.

This is because it is not managed by fastmigrate. Please do one of the following:

1. Create a new, managed db using `fastmigrate.create_db()` or
`fastmigrate_create_db`

2. Enroll your existing database, as described in
https://answerdotai.github.io/fastmigrate/enrolling.html""",file=stderr)
            return False

        # Get current version
        current_version = get_db_version(db_path)

        # Get all migration scripts
        try:
            migration_scripts = get_migration_scripts(migrations_dir)
        except ValueError as e:
            print(f"Error: {e}", file=stderr)
            return False

        # Find pending migrations
        pending_migrations = {
            version: path
            for version, path in migration_scripts.items()
            if version > current_version
        }

        if not pending_migrations:
            if verbose:
                print(f"Database is up to date (version {current_version})")
            return True

        # Sort migrations by version
        sorted_versions = sorted(pending_migrations.keys())

        # Execute migrations
        for version in sorted_versions:
            script_path = pending_migrations[version]
            script_name = script_path.name

            if verbose:
                print(f"Applying migration {version}: {script_name}")

            # Each script will open its own connection

            # Execute the migration script
            success = execute_migration_script(db_path, script_path)

            if not success:
                # Show summary of failure - always show errors regardless of verbose flag
                stats["failed"] += 1
                print(f"""Migration failed: {script_path}
  • {stats['applied']} migrations applied
  • {stats['failed']} migrations failed""", file=stderr)

                return False

            stats["applied"] += 1

            # Update version
            _set_db_version(db_path, version)
            if verbose:
                print(f"✓ Database updated to version {version}")

        # Show summary of successful run
        if stats["applied"] > 0 and verbose:
            print("\nMigration Complete")
            print(f"  • {stats['applied']} migrations applied")
            print(f"  • Database now at version {sorted_versions[-1]}")

        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}", file=stderr)
        return False
    except Exception as e:
        print(f"Error: {e}", file=stderr)
        return False

def get_db_schema(db_path: Path) -> str:
    """Get the SQL schema of a SQLite database file.

    This function retrieves the CREATE statements for all tables,
    indices, triggers, and views in the database.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        str: The SQL schema as a string

    Raises:
        FileNotFoundError: If database file doesn't exist
        sqlite3.Error: If unable to access the database
    """

    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database does not exist: {db_path}")

    # Preferred implementation: use APSW's `.schema` output if available.
    # APSW is an optional dependency; if it's not installed we fall back to
    # `sqlite3` introspection.
    try:
        from apsw import Connection  # type: ignore
        from apsw.shell import Shell  # type: ignore

        conn = Connection(str(db_path))
        out = StringIO()
        shell = Shell(stdout=out, db=conn)
        shell.process_command(".schema")
        sql = out.getvalue()
    except Exception:
        # Fallback: extract CREATE statements from sqlite_master.
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(
                """
                SELECT sql FROM sqlite_master
                WHERE sql IS NOT NULL AND type IN ('table', 'index', 'trigger', 'view')
                ORDER BY type, name
                """
            ).fetchall()
            sql = "\n\n".join(r[0].rstrip(";") + ";" for r in rows if r and r[0])
        finally:
            conn.close()

    if "CREATE TABLE" in sql:
        sql = sql.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS")
    if "CREATE INDEX" in sql:
        sql = sql.replace("CREATE INDEX", "CREATE INDEX IF NOT EXISTS")
    return sql
