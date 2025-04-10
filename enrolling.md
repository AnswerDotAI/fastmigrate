# Enrolling an existing db in fastmigrate

If you use fastmigrate with valid migration scripts, fastmigrate can guarantee the version of your database presented to your application code. This is the value of managed migrations.

However, to provide this guarantee, you need your database to be managed by fastmigrate. If you created the database with fastmigrate (using `create_db`), then it is managed.

But what if you are starting with an application built outside of fastmigrate, and you want to _enroll_ the database in fastmigrate? Here is how to think about it, and how to do it correctly:

To clarify the background: the key invariant which we need to maintain is this: *any database which has a fastmigrate version number (like 1, or like 3) is exactly in the state which would be produced by the migration script with that version number (like by `0001-initialize.sql` or `0003-unify-users.sql`).* 

Now if you create a db with fastmigrate, it is created with version 0, and the version only advances as a result of running migration scripts. So this maintains the invariant.

But if you are enrolling an existing db into fastmigrate, then you need to do three things.

- First, write a migration script `0001-initialize.sql` which will produce the schema of the database which you are working with right now.

    Why? You need this so that, when you are starting fresh instances of your application, fastmigrate can create a database which is equivalent to what you have created now. The easiest way to create this script is to run `sqlite3 data.db .schema > 0001-initialize.sql` on your current database, which will create a sql file `0001-initialize.sql` which creates a fresh db with the same schema as your current db.
   
    This is now your first migration script. Because it matches the current state of your current database, it will not be run on your current database. But it will ensure that newly created databases match your current database.
   
    From an abundance of caution, you should use it to create a db and confirm that it is indeed equivalent to your current db.
   
- Second, manually modify your current data to add fastmigrate version tag and set its version to 1. You can do this by using fastmigrate's internal API. Doing this constitutes asserting that the db is in fact in the state which would be produced by the migration script 0001. After doing this, fastmigrate will recognize your db as managed. Here is how to do it:

```python
from fastmigrate.core import _ensure_meta_table, _set_db_version
_ensure_meta_table("path/to/data.db")
_set_db_version("path/to/data.db",1)
```

- Third, update your application code.

    You should update it so that it no longer manually creates and initializes a database if it is missing by itself (as it might do now), but instead uses fastmigrate to create the db and to run the migrations, as is shown in the readme. You should check the migration scripts into version control alongside your application code. Your application code should now all be written under the assumption that it will find the database in the state defined by the highest-numbered migration script in the repo.
    

