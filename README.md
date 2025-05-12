## fastmigrate

The fastmigrate library helps with structured migration of data in SQLite. That is, it gives you a way to specify and run a sequence of updates to your database schema, while preserving user data.

### Installation

fastmigrate is available to install from pypi.

```bash
pip install fastmigrate

# or if using uv add it to your pyproject.toml
uv add fastmigrate
```

To run all the tests, you also need to install the sqlite3 executable installed on your system.

### How to use fastmigrate in your app

Once you have added a `migrations/` directory to your app, you would typically use fastmigrate in your application code like so:

```python
from fastmigrate.core import create_db, run_migrations

# At application startup:
db_path = "path/to/database.db"
migrations_dir = "path/to/migrations"

# Create/verify there is a versioned database, or else fail
current_version = create_db(db_path)

# Apply any pending migrations
success = run_migrations(db_path, migrations_dir, verbose=False)
if not success:
    # Handle migration failure
    print("Database migration failed!")
```

This will create a db if needed. Then, fastmigrate will detect every validly-named migration script in the migrations directory, select the ones with version numbers greater than the current db version number, and run the migration in alphabetical order, updating the db's version number as it proceeds, stopping if any migration fails.

This will guarantee that all subsequent code will encounter a database at the schema version defined by your highest-numbered migration script. So when you deploy updates to your app, those updates should include any new migration scripts along with modifications to code, which should now expect the new db schema.

If you get the idea and are just looking for a reminder about a reasonable workflow for safely adding a new migration please see this note on [safely adding migrations](./adding_migrations.md)

### Key concepts:

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

### What fastmigrate guarantees

The point of the system is that if you adopt it, fastmigrate offers the following two guarantees:

> [!NOTE]
> Fastmigrate will never leave a database marked with an incorrect version without signalling an error, if *your* migration scripts reliably exit with an error code whenever they fail.
> 
> Furthermore, fastmigrate will never leave a database corrupted, if *your* migration scripts always leave the db unmodified when they fail. (This is relatively easy with sql-based scripts, since they can use sql rollback).

To get these guarantees, you only need to use fastmigrate's public commands and APIs to handle creating the db and running migrations (unless you are [enrolling an existing db](./enrolling.md)).

One easy way to experiment with these core operations, for instance when testing a new migration, is via the command line tool. 

### How to use fastmigrate from the command line

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
   fastmigrate_run_migrations --db path/to/data.db
   ```
   Run all needed migrations on the db. Fails if a migration fails, or if there is no managed db at the path. This is equivalent to calling `fastmigrate.run_migrations()`


### How to enroll an existing, unversioned database into fastmigrate

FastMigrate needs to manage database versioning in order to run migrations.

So if you already have a database which was created outside of fastmigrate, then you need to enroll it.

Please see the dedicated note on [enrolling an existing db](./enrolling.md).

### Miscellaneous Considerations

1. **Unversioned Databases**: FastMigrate will refuse to run migrations on existing databases that don't have a _meta table with version information.

2. **Sequential Execution**: Migrations are executed in order based on their index numbers. If migration #3 fails, migrations #1-2 remain applied and the process stops.

3. **Version Integrity**: The database version is only updated after a migration is successfully completed.

4. **External Side Effects**: Python and Shell scripts may have side effects outside the database (file operations, network calls) that are not managed by fastmigrate.

5. **Database Locking**: During migration, the database may be locked. Applications should not attempt to access it while migrations are running.

6. **Backups**: For safety, you can use the `--backup` option to create a backup before running migrations.

### Contributing

To contribute to fastmigrate, create an editable install with the `dev` [dependency group](https://peps.python.org/pep-0735) using your favorite package manager.

For example, with uv (preferred):

```bash
uv sync
```

or with pip 25.1:

```bash
pip install -e . --group dev
```

We currently don't check in the `uv.lock` file.
