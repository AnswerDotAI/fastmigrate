# Safely adding a new migration

So you need to modify your db schema? And you want to be very sure you are doing it correctly?

This page is a suggested workflow, just to remind you how to go about this process, assuming your application is already using fastmigrate.

If your app is using fastmigrate, then two things should already be in your codebase. First, there will be a migrations directory, which contains migration scripts numbered like `0001-initialize.sql`, `0002-next-thing.py`, `0003-another-thing.sql`, and so on, all the way up to `0010-latest-thing.sql` (for instance).

Second your app will have initialization code which looks a bit like this:

```python
from fastmigrate.core import create_db, run_migrations
db_path = "path/to/database.db"
migrations_dir = "path/to/migrations/directory/"
current_version = create_db(db_path)
success = run_migrations(db_path, migrations_dir, verbose=False)
if not success:
    # Handle migration failure
    print("Database migration failed!")
```

To recap, what is going on here is that the highest-numbered migration script (`0010-latest-thing.sql` in this example), defines the *guaranteed version of your database*. And the initialization code is what *enforces that guarantee*. After the initialization code has run successfully, the rest of your app can and should assume that your database is at version 10.

So what does this imply about adding a new migration?

Suppose that you want to change your db schema, which does "one more thing". This defines a *next version* of your database. Since the current version of your db is 10, the next version of your database will be 11. So the first thing you should do is write the migration script which updates your database from its current version to the next version, as a file named `0011-one-more-thing.py` (or .sql or .sh).

The second thing you should do is update all of your application code so that it now expects to see version 11 of your database. That is, all the code which runs after the init code may assume migration has taken place. It does not need conditional paths to handle the older version, version 10, because the fastmigrate initialization code will have already taken care of running the migration script if necessary, and it will have succeeded or failed.

Those two changes you made -- adding a new migration script, and updating your application code -- should ideally be added to your version control *with the same commit* since they are coordinated changes. There will never come a moment when you want code which expects version 10 to see a database at version 11, nor a moment when you want code which expects version 11 to see a database at version 10. So it is unwise to check in these changes separately. 

Now, of course, test your application locally before pushing or deploying.

How? In addition to normal application testing, you might want to test your migration script in isolation from your application code. The easiest way to do that is by using the fastmigrate command line tool. If you run `fastmigrate --migrations /path/to/migrations --db /path/to/data.db`, with `data.db` at version 10 and an 0011 script in `migrations/`, then it will update the data to version 11 in isolation. You can then manually inspect the migrated database using sqlite3 or any other tool of your choice.






