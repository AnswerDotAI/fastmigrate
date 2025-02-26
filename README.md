## fastmigrate

The fastmigrate library helps you with structured migration of data in SQLite. That is, it gives you a way to change the schema of your database, while preserving user data.

Here's how it works for a user.

In a directory containing a `.fastmigrate` file (which will generally be the project root), the user calls `fastmigrate`. By default, this will look off the current directory for a migrations subdirectory called `migrations` and a database in `data/database.db`. These values can also be overriden by CLI arguments or by values set in the `.fastmigrate` configuration file, which is in ini format.

It will then detect every validly-named file in the migrations directory, select the ones with version numbers greater than the current db version number, and apply the files in alphabetical order, updating the db's version number as it proceeds, stopping if any migration fails.

### Key concepts:

- the **version number** of a database:
  - this is an `int` value stored in a table `_meta` in a field called `version`. This table will be enforced to have exactly one row. This value will be the "db version value" of the last migration script which was run on that database.
  
- the **migrations directory** is a directory which contains only migration scripts.

- a **migration script** must be:
  - a file which conforms to the "FastMigrate naming rule"
  - one of the following:
     - a .py or .sh file. In this case, fastmigrate will execute the file, pass the path to the db as the first positional argument. Fastmigrate will interpret a non-zero exit code as failure.
     - a .sql file. In this case, fastmigrate will execute the SQL script. If any statement fails, the whole migration is rolled back.
  
- the **FM naming rule** is that every migration script must have a name matching this pattern: `[index]-[description].[fileExtension]`, where `[index]` must be a string representing 4-digit integer. This naming convention defines the order in which scripts should be run.

- **attempting a migration** is:
  - determining the current version of a database
  - determining if there are any migration scripts with versions higher than the db version
  - trying to run those scripts

### Rollback Guarantees

FastMigrate provides a robust backup/restore mechanism to ensure database integrity:

1. **Full Database Backup**: Before executing each migration script (SQL, Python, or Shell), FastMigrate creates a complete backup of the database file.

2. **File-Based Rollback**: FastMigrate uses a file-based approach to ensure safety:
   - The entire database file is backed up before each migration
   - This approach works consistently for all script types (.sql, .py, .sh)
   - If any script fails, the entire database file is restored to its previous state

3. **Automatic Restore on Failure**: If a migration fails for any reason, FastMigrate:
   - Detects the failure (SQL error, non-zero exit code, exception)
   - Automatically restores the database from backup
   - Leaves the database in the state it was in before the failed migration

4. **Version Integrity**: The database version is only updated after a migration is successfully completed.

### Important Considerations

1. **All-or-Nothing Migrations**: Each migration script (SQL, Python, or Shell) is treated as a single unit - either it succeeds completely or the database is restored to its state before the migration.

2. **External Side Effects**: Python and Shell scripts may have side effects outside the database (file operations, network calls) that can't be rolled back.

3. **Cross-Migration Dependencies**: Migrations are executed sequentially. If migration #3 fails, migrations #1-2 remain applied.

4. **Database Locking**: During migration, the database may be locked. Applications should not attempt to access it while migrations are running.

5. **Interactive Mode**: Using the `--interactive` flag allows you to selectively apply migrations, providing finer control over the migration process.

6. **Dry Run**: The `--dry-run` flag allows you to preview migrations that would be applied without making any changes.

