-- This migration contains a deliberate SQL error to test rollback
CREATE TABLE tags (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

-- This INSERT will fail due to non-existent column
INSERT INTO tags (id, name, description) VALUES (1, 'sql', 'This will fail');