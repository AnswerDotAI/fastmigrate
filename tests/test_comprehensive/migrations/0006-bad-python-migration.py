#!/usr/bin/env python3
"""Python migration with deliberate failure to test rollback."""

import sqlite3
import sys

def migrate(db_path):
    """This migration will fail deliberately."""
    conn = sqlite3.connect(db_path)
    
    try:
        # Create a table first (this will succeed)
        conn.execute("""
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            )
        """)
        
        # Add some data (this will succeed)
        conn.execute("INSERT INTO categories (name) VALUES ('general')")
        
        # This will fail because the table doesn't have a 'description' column
        conn.execute("INSERT INTO categories (name, description) VALUES ('news', 'News articles')")
        
        conn.commit()
        return 0
    except Exception as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        conn.rollback()
        return 1
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python 0006-bad-python-migration.py <db_path>", file=sys.stderr)
        sys.exit(1)
    
    sys.exit(migrate(sys.argv[1]))