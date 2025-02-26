#!/usr/bin/env python
"""Migration that will fail with a non-zero exit code."""

import sqlite3
import sys


def main() -> int:
    """Run the migration."""
    if len(sys.argv) < 2:
        print("Error: Database path not provided")
        return 1
    
    db_path = sys.argv[1]
    conn = sqlite3.connect(db_path)
    
    # Intentionally fail with a non-zero exit code
    print("This migration script is intentionally failing with exit code 1")
    return 1


if __name__ == "__main__":
    sys.exit(main())