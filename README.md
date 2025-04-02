## fastmigrate

The fastmigrate library helps you with structured migration of data in SQLite. That is, it gives you a way to specify and run a sequence of updates to your database schema, while preserving user data.

### Programmatic Usage

Once you have added a `migrations/` directory to your app, you would typically use fastmigrate in your application code like so:

```python
from fastmigrate.core import ensure_versioned_db, run_migrations

# At application startup:
db_path = "path/to/database.db"
migrations_dir = "path/to/migrations"

# Create/verify there is a versioned database, or else fail
current_version = ensure_versioned_db(db_path)

# Apply any pending migrations
success = run_migrations(db_path, migrations_dir, verbose=False)
if not success:
    # Handle migration failure
    print("Database migration failed!")
```

fastmigrate will then detect every validly-named migration script in the migrations directory, select the ones with version numbers greater than the current db version number, and apply the files in alphabetical order, updating the db's version number as it proceeds, stopping if any migration fails.

This will guarantee that all subsequent code will enccounter a database at the schema version defined by your highest-numbered migration script. So when you deploy updates to your app, those updates should include any new migration scripts along with modifications to code, which should now expect the new db schema.

### Key concepts:

Fastmigrate implements the standard database migration pattern, so the key concepts may be familiar.

- the **version number** of a database:
  - this is an `int` value stored in a table `_meta` in a field called `version`. This table will be enforced to have exactly one row. This value will be the "db version value" of the last migration script which was run on that database.
  
- the **migrations directory** is a directory which contains the migration scripts, which initialize the db to its initial version and update it to the latest version as needed.

- a **migration script** must be:
  - a file which conforms to the "fastmigrate naming rule"; and,
  - one of the following:
     - a .py or .sh file. In this case, fastmigrate will execute the file, pass the path to the db as the first positional argument. Fastmigrate will interpret a non-zero exit code as failure.
     - a .sql file. In this case, fastmigrate will execute the SQL script against the database.
  
- the **fastmigrate naming rule** is that every migration script must have a name matching this pattern: `[index]-[description].[fileExtension]`, where `[index]` must be a string representing 4-digit integer. This naming convention defines the order in which scripts should be run.

- **attempting a migration** is:
  - determining the current version of a database
  - determining if there are any migration scripts with versions higher than the db version
  - trying to run those scripts

### Command-line Usage

To familiarize yourself with its action, or in development, you might want to run fastmigrate from the command line. 

When you run `fastmigrate`, it will look for migration scripts in `./migrations/` and a database at `./data/database.db`. These values can also be overridden by CLI arguments or by values set in the `.fastmigrate` configuration file, which is in ini format.

### Command Line Options

1. **Basic Usage**:
   ```
   fastmigrate
   ```
   This will use the defaults, looking for migrations in `./migrations/` and the database in `./data/database.db`.

2. **Specify Paths**:
   ```
   fastmigrate --db path/to/database.db --migrations path/to/migrations
   ```

3. **Create Database**:
   ```
   fastmigrate --createdb
   ```
   Creates an empty database with the _meta table if it doesn't exist.

4. **Database Backup**:
   ```
   fastmigrate --backup
   ```
   Creates a timestamped backup of the database before running any migrations.
   The backup file will be named `database.db.YYYYMMDD_HHMMSS.backup`.

### Unversioned Databases

FastMigrate requires databases to be properly versioned before running migrations. If you attempt to run migrations on an unversioned database:

1. `run_migrations()` will fail and return `False`.
2. The CLI will display an error message and exit with a non-zero status.

To create a new versioned database:
- Use `ensure_versioned_db()` in your code, or
- Use the CLI with the `--createdb` flag (only works for new databases)

To version an existing database with data:
1. Manually verify which migrations have already been applied
2. Use `set_db_version()` to set the appropriate version number

### Important Considerations

1. **Unversioned Databases**: FastMigrate will refuse to run migrations on existing databases that don't have a _meta table with version information.

2. **Sequential Execution**: Migrations are executed in order based on their index numbers. If migration #3 fails, migrations #1-2 remain applied and the process stops.

3. **Version Integrity**: The database version is only updated after a migration is successfully completed.

4. **External Side Effects**: Python and Shell scripts may have side effects outside the database (file operations, network calls) that are not managed by fastmigrate.

5. **Database Locking**: During migration, the database may be locked. Applications should not attempt to access it while migrations are running.

6. **Backups**: For safety, you can use the `--backup` option to create a backup before running migrations.

