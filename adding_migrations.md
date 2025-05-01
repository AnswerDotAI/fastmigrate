# How to add a new migration to your app

So you need to modify your db schema? And you want to be very sure you are doing it correctly?

This page is a suggested workflow to remind you how to go about this process, assuming your application is already using fastmigrate.

### What should already be in your app

If your app is using fastmigrate, then two things should already be in your codebase.

First, there will be a migrations directory, which contains migration scripts numbered like `0001-initialize.sql`, `0002-next-thing.py`, `0003-another-thing.sql`, and so on, all the way up to `0010-latest-thing.sql` (for instance).

Second, your app will either have initialization code which looks a bit like this:

```python
from fastmigrate.core import create_db, run_migrations
db_path = "path/to/data.db"
migrations_dir = "path/to/migrations/"
current_version = create_db(db_path)
success = run_migrations(db_path, migrations_dir, verbose=False)
if not success:
    # Handle migration failure
    print("Database migration failed!")
```

Or you are relying on the fastmigrate command line tool to do this for you, in which case you will have a command like this in your deployment script:

```bash
fastmigrate_create_db --db /path/to/data.db
fastmigrate_backup_db --db /path/to/data.db
fastmigrate_run_migrations --migrations /path/to/migrations/ --db /path/to/data.db
```

To recap, what is going on here is that the highest-numbered migration script (`0010-latest-thing.sql` in this example), defines the *guaranteed version of your database*. The initialization code is what *enforces that guarantee*. After the initialization code has run successfully, the rest of your app can and should assume that your database is at version 10.

### What to add to your app

So what does this imply about adding a new migration?

Suppose that you want to change your db schema, so that it does "one more thing". This defines a *next version* of your database. Since the current version of your db is 10, the next version of your database will be 11.

1. So the first thing you should do is write the migration script which updates your database from its current version to the next version, as a file named `0011-one-more-thing.py` (or .sql or .sh).

2. The second thing you should do is update all of your application code so that it now expects to see version 11 of your database. That is, all the code which runs after the init code should assume migration has taken place. It does not need conditional paths to handle the older version, version 10, because the fastmigrate initialization code is responsible for running the migration script if necessary, and it will have succeeded or explicitly failed.

Those two changes you made -- adding a new migration script, and updating your application code -- should ideally be added to your version control *with the same commit* since they are coordinated changes. There will never come a moment when you want code which expects version 10 to see a database at version 11, nor a moment when you want code which expects version 11 to see a database at version 10. So it is unwise to check in these changes separately.

> Note: if you add a .sql migration script, you need have the sqlite3 binary installed on your system.

### How to test

Of course, test your application locally before pushing or deploying.

How? In addition to normal application testing, you might want to test your migration script in isolation from your application code. The easiest way to do that is by using the fastmigrate command line tool. If you run `fastmigrate_run_migrations /path/to/migrations --db /path/to/data.db`, with `data.db` at version 10 and an 0011 script in `migrations/`, then it will update the data to version 11 in isolation. You can then manually inspect the migrated database using sqlite3 or any other tool of your choice.

The fundamental rule to keep in mind with migrations is that you only ever add an additional migration. You never go back and change old ones. You could say the collection of migrations is _append only_. This is what makes them reliable, because it is what guarantees that they are always working from a known state. But it is also what can make the workflow for adding a new migration unfamiliar, since you need to think in terms of the _diffs_ to the database, even while your application code is usually thinking in terms of the database's instantaneous _state_.



