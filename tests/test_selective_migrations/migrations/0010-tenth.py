#!/usr/bin/env python
"""Migration 0010: Tenth migration (large gap)"""

import sqlite3
import sys


def main() -> int:
    """Run the migration."""
    if len(sys.argv) < 2:
        print("Error: Database path not provided")
        return 1
    
    db_path = sys.argv[1]
    conn = sqlite3.connect(db_path)
    
    try:
        conn.execute("""
        INSERT INTO migrations_log (migration_id, description) 
        VALUES (10, 'Tenth migration executed via Python')
        """)
        conn.commit()
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())