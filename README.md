## fastmigrate

The fastmigrate library helps you with structured migration of data in SQLite. That is, it gives you a way to change the schema of your database, while preserving user data.

Here's how it works for a user.

In a directory containing a `.fastmigrate` file (which will generally be the project root), the user calls `fastmigrate`. By default, this will look for migration scripts in `./migrations/` and a database at `./data/database.db`. These values can also be overridden by CLI arguments or by values set in the `.fastmigrate` configuration file, which is in ini format.

It will then detect every validly-named file in the migrations directory, select the ones with version numbers greater than the current db version number, and apply the files in alphabetical order, updating the db's version number as it proceeds, stopping if any migration fails.

### Key concepts:

- the **version number** of a database:
  - this is an `int` value stored in a table `_meta` in a field called `version`. This table will be enforced to have exactly one row. This value will be the "db version value" of the last migration script which was run on that database.
  
- the **migrations directory** is a directory which contains only migration scripts.

- a **migration script** must be:
  - a file which conforms to the "FastMigrate naming rule"
  - one of the following:
     - a .py or .sh file. In this case, fastmigrate will execute the file, pass the path to the db as the first positional argument. Fastmigrate will interpret a non-zero exit code as failure.
     - a .sql file. In this case, fastmigrate will execute the SQL script against the database.
  
- the **FM naming rule** is that every migration script must have a name matching this pattern: `[index]-[description].[fileExtension]`, where `[index]` must be a string representing 4-digit integer. This naming convention defines the order in which scripts should be run.

- **attempting a migration** is:
  - determining the current version of a database
  - determining if there are any migration scripts with versions higher than the db version
  - trying to run those scripts

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

### Important Considerations

1. **Sequential Execution**: Migrations are executed in order based on their index numbers. If migration #3 fails, migrations #1-2 remain applied and the process stops.

2. **Version Integrity**: The database version is only updated after a migration is successfully completed.

3. **External Side Effects**: Python and Shell scripts may have side effects outside the database (file operations, network calls) that are not managed by fastmigrate.

4. **Database Locking**: During migration, the database may be locked. Applications should not attempt to access it while migrations are running.

5. **Backups**: For safety, you can use the `--backup` option to create a backup before running migrations.

