# fastmigrate

The fastmigrate library helps with structured migration of data in SQLite. That is, it gives you a way to specify and run a sequence of updates to your database schema, while preserving user data.

## Installation

fastmigrate is available to install from pypi.

```bash
pip install fastmigrate

# or if using uv add it to your pyproject.toml
uv add fastmigrate
```

Fastmigrate itself does not require the external ``sqlite3`` command-line tool.
If you choose to write ``.sh`` migrations that invoke ``sqlite3`` yourself, you'll
need it installed, but ``.sql`` migrations run via Python's built-in sqlite3.

## How to use fastmigrate in your app

Once you have added a `migrations/` directory to your app, you would typically use fastmigrate in your application code like so:

```python
from fastmigrate import create_db, run_migrations, setup_logging

# At application startup:
db_path = "path/to/database.db"
migrations_dir = "path/to/migrations"

# Create/verify there is a versioned database
current_version = create_db(db_path)

# Optional: enable debug logs from fastmigrate
setup_logging(verbose=True)

# Apply any pending migrations
if not run_migrations(db_path, migrations_dir):
    print("Database migration failed!")
```

This will create a db if needed. Then, fastmigrate will detect every validly-named migration script in the migrations directory, select the ones with version numbers greater than the current db version number, and run the migration in alphabetical order, updating the db's version number as it proceeds, stopping if any migration fails.

This will guarantee that all subsequent code will encounter a database at the schema version defined by your highest-numbered migration script. So when you deploy updates to your app, those updates should include any new migration scripts along with modifications to code, which should now expect the new db schema.

If you get the idea and are just looking for a reminder about a reasonable workflow for safely adding a new migration please see this note on [safely adding migrations](./docsrc/adding_migrations.qmd)

## Key concepts:

Fastmigrate implements the standard database migration pattern, so these key concepts may be familiar.

- the **version number** of a database:
  - this is an `int` value stored in a single-row table `_meta` in the field `version`. This is "db version", which is also the version of the last migration script which was run on that database.
- the **migrations directory** contains the migration scripts, which initialize the db to its initial version 1 and update it to the latest version as needed.
- every valid **migration script** must:
  - conform to the "fastmigrate naming rule"
  - be one of the following:
     - a .py or .sh file. In this case, fastmigrate will execute the file, pass the path to the db as the first positional argument. Fastmigrate will interpret a non-zero exit code as failure.
     - a .sql file. In this case, fastmigrate will execute the SQL script against the database.
  - terminate with an exit code of 0, if and only if it succeeds
  - (ideally) leave the db unmodified, if it fails
- the **fastmigrate naming rule** is that every migration script match this naming pattern: `[index]-[description].[fileExtension]`, where `[index]` must be a string representing 4-digit integer. This naming convention defines the order in which scripts will run and the db version each migration script produces.
- **attempting a migration** is:
  - determining the current version of a database
  - determining if there are any migration scripts with versions higher than the db version
  - trying to run those scripts

When Fastmigrate encounters an error, it stops. It does not attempt to roll back or reverse. Therefore, if you want to ensure your migrations are never left half-completed mid-script, add appropriate transactions inside your sql.

## Using fastmigrate with non-SQLite databases

Fastmigrate is **SQLite-first** by default, but you can make it **database-independent**
by providing a backend adapter at:

```
<your migrations dir>/config.py
```

When this file exists, :func:`fastmigrate.run_migrations` will:

- load this module dynamically
- call your adapter hooks to:
  - create the ``_meta`` table (if needed)
  - read/update the version number
  - execute ``.sql`` migrations using your database driver
- still run ``.py`` and ``.sh`` migrations the same way as usual (passing
  ``str(db)`` as the first positional argument)

### Minimal required functions in ``config.py``

Each hook may be **sync or async**. If a hook returns an awaitable/coroutine,
fastmigrate will automatically await it.

```python
def get_connection(db): ...
def ensure_meta_table(conn): ...
def get_version(conn) -> int: ...
def set_version(conn, version: int): ...
def execute_sql(conn, sql: str): ...

# optional
def close_connection(conn): ...
```

### Example: SQLAlchemy adapter (SQLite)

```python
# migrations/config.py
from sqlalchemy import create_engine, text

def get_connection(db): return create_engine(f"sqlite+pysqlite:///{db}")
def close_connection(engine): engine.dispose()

def ensure_meta_table(engine):
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS _meta (id INTEGER PRIMARY KEY, version INTEGER NOT NULL)"
        )
        row = conn.exec_driver_sql("SELECT version FROM _meta WHERE id=1").fetchone()
        if row is None: conn.exec_driver_sql("INSERT INTO _meta (id, version) VALUES (1, 0)")

def get_version(engine):
    with engine.connect() as conn:
        row = conn.exec_driver_sql("SELECT version FROM _meta WHERE id=1").fetchone()
        return int(row[0]) if row else 0

def set_version(engine, version: int):
    with engine.begin() as conn:
        conn.exec_driver_sql("DELETE FROM _meta WHERE id=1")
        conn.exec_driver_sql("INSERT INTO _meta (id, version) VALUES (1, ?)", (int(version),))

def execute_sql(engine, sql: str):
    with engine.begin() as conn:
        # Basic split; feel free to use something more robust for your DB
        for stmt in [s.strip() for s in sql.split(";") if s.strip()]: conn.exec_driver_sql(stmt)
```
### Sync or async hooks

Each function may be sync or async. If any hook returns an awaitable, fastmigrate
automatically awaits it so adapters can be built on asyncpg, SQLAlchemy asyncio,
psycopg3 async mode, etc.

## How to use fastmigrate from the command line

When you run `fastmigrate`, it will look for migration scripts in `./migrations/` and a database at `./data/database.db`. These values can also be overridden by CLI arguments or by values set in the `.fastmigrate` configuration file, which is in ini format. But you can also provide them as with the command line arguments `--db` and `--migrations`.

Here are some commands:

1. **Create Database**:
   ```
   fastmigrate_create_db --db /path/to/data.db
   ```
   If no database is there, create an empty database with version=0. If a versioned db is there, do nothing. If an unversioned db or anything else is there, exit with an error code. This is equivalent to calling `fastmigrate.create_db()`

2. **Check a db**
   ```
   fastmigrate_check_version --db /path/to/data.db
   ```
   This will report the version of both fastmigrate and the db.

3. **Backup a db**:
   ```
   fastmigrate_backup_db --db /path/to/data.db
   ```
   Backup the database with a timestamped filename ending with a .backup extention. This is equivalent to calling `fastmigrate.backup_db()`
   
4. **Run migrations**:
   ```
   fastmigrate_run_migrations --db path/to/data.db --verbose
   ```
   Run all needed migrations on the db. Fails if a migration fails, or if there is no managed db at the path. This is equivalent to calling `fastmigrate.run_migrations()`. Use `--verbose` to enable debug-level logs.

5. **Enroll an existing db**:
   ```
   fastmigrate_enroll_db --db path/to/data.db
   ```
   Enroll an existing SQLite database for versioning, adding a default initial migration called `0001-initial.sql`, then running it. Running the initial migration will set the version to 1. This is equivalent to calling `fastmigrate.enroll_db()`

## How to enroll an existing, unversioned database into fastmigrate

FastMigrate needs to manage database versioning in order to run migrations.

So if you already have a database which was created outside of fastmigrate, then you need to enroll it.

Please see the dedicated note on [enrolling an existing db](./docsrc/enrolling.qmd).

## Miscellaneous Considerations

1. **Unversioned Databases**: FastMigrate will refuse to run migrations on existing databases that don't have a _meta table with version information.
2. **Sequential Execution**: Migrations are executed in order based on their index numbers. If migration #3 fails, migrations #1-2 remain applied and the process stops.
3. **Version Integrity**: The database version is only updated after a migration is successfully completed.
4. **External Side Effects**: Python and Shell scripts may have side effects outside the database (file operations, network calls) that are not managed by fastmigrate.
5. **Database Locking**: During migration, the database may be locked. Applications should not attempt to access it while migrations are running.
6. **Backups**: For safety, you can use the `--backup` option to create a backup before running migrations.

## Contributing

To contribute to fastmigrate, create an editable install with the `dev` [dependency group](https://peps.python.org/pep-0735) using your favorite package manager.

For example, with uv (preferred):

```bash
uv sync
```

or with pip 25.1:

```bash
pip install -e . --group dev
```
