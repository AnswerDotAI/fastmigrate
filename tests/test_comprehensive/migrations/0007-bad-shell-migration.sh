#!/bin/sh
# Shell migration with deliberate failure to test rollback

DB_PATH="$1"
if [ -z "$DB_PATH" ]; then
  echo "Usage: $0 <db_path>"
  exit 1
fi

# This part will succeed
sqlite3 "$DB_PATH" <<EOF
CREATE TABLE IF NOT EXISTS tags_extended (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  color TEXT DEFAULT 'blue'
);

INSERT INTO tags_extended (name) VALUES ('featured');
EOF

# This command will fail (non-existent table)
sqlite3 "$DB_PATH" "INSERT INTO non_existent_table (name) VALUES ('will fail');"

# We'll never reach this point due to the error above
exit 0