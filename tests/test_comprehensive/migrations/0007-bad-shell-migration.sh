#!/bin/sh
# Shell migration with deliberate failure to test error handling.

set -e

DB_PATH="$1"
if [ -z "$DB_PATH" ]; then
  echo "Usage: $0 <db_path>"
  exit 1
fi

# Part 1: succeed
python3 - "$DB_PATH" <<'PY'
import sqlite3
import sys

db_path = sys.argv[1]
conn = sqlite3.connect(db_path)
conn.executescript(
    """
CREATE TABLE IF NOT EXISTS tags_extended (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  color TEXT DEFAULT 'blue'
);

INSERT INTO tags_extended (name) VALUES ('featured');
"""
)
conn.commit()
conn.close()
PY

# Part 2: fail (non-existent table)
python3 - "$DB_PATH" <<'PY'
import sqlite3
import sys

db_path = sys.argv[1]
conn = sqlite3.connect(db_path)
conn.execute("INSERT INTO non_existent_table (name) VALUES ('will fail');")
conn.commit()
conn.close()
PY

# We'll never reach this point because `set -e` + the failing statement above.
exit 0
