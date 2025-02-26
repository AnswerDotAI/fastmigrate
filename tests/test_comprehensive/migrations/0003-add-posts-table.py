#!/usr/bin/env python3
"""Create posts table and add sample data."""

import sqlite3
import sys

def migrate(db_path):
    """Create posts table and add sample post for demo."""
    conn = sqlite3.connect(db_path)
    
    try:
        # Create posts table with foreign key to users
        conn.executescript("""
            CREATE TABLE posts (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            
            -- Add sample post for admin user
            INSERT INTO posts (user_id, title, content)
            SELECT id, 'First Post', 'Hello World!' FROM users WHERE username = 'admin';
        """)
        
        conn.commit()
        return 0  # Success
    except Exception as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        conn.rollback()
        return 1  # Error
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python 0003-add-posts-table.py <db_path>", file=sys.stderr)
        sys.exit(1)
    
    sys.exit(migrate(sys.argv[1]))