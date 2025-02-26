#!/bin/sh
# Create comments table and add sample data using a shell script

DB_PATH="$1"
if [ -z "$DB_PATH" ]; then
  echo "Usage: $0 <db_path>"
  exit 1
fi

# Create table and add sample data
sqlite3 "$DB_PATH" <<EOF
-- Create comments table
CREATE TABLE comments (
  id INTEGER PRIMARY KEY,
  post_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (post_id) REFERENCES posts(id),
  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Add sample comment
INSERT INTO comments (post_id, user_id, content)
SELECT p.id, u.id, 'Great first post!'
FROM posts p
JOIN users u ON u.username = 'admin'
LIMIT 1;
EOF

# Check execution status
if [ $? -eq 0 ]; then
  exit 0
else
  echo "Error executing SQL script"
  exit 1
fi