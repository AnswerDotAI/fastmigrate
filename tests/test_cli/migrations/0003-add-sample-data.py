#!/usr/bin/env python
"""Migration 0003: Add sample data"""

import sqlite3
import sys


def main() -> int:
    """Run the migration."""
    if len(sys.argv) < 2:
        print("Error: Database path not provided")
        return 1
    
    db_path = sys.argv[1]
    conn = sqlite3.connect(db_path)
    
    # Add sample users
    conn.executescript("""
    INSERT INTO users (username, email) VALUES 
        ('admin', 'admin@example.com'),
        ('user1', 'user1@example.com'),
        ('user2', 'user2@example.com');
        
    -- Add sample posts
    INSERT INTO posts (user_id, title, content) VALUES
        (1, 'Welcome to FastMigrate', 'This is a sample post by the admin'),
        (2, 'My First Post', 'This is a sample post by user1'),
        (3, 'Hello World', 'This is a sample post by user2');
    """)
    
    conn.commit()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())