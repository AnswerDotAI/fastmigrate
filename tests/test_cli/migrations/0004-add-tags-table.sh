#!/bin/sh
# Migration 0004: Add tags table and relationship

DB_PATH="$1"

sqlite3 "$DB_PATH" <<EOF
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE post_tags (
    post_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (post_id, tag_id),
    FOREIGN KEY (post_id) REFERENCES posts(id),
    FOREIGN KEY (tag_id) REFERENCES tags(id)
);

-- Add some sample tags
INSERT INTO tags (name) VALUES ('migration');
INSERT INTO tags (name) VALUES ('sqlite');
INSERT INTO tags (name) VALUES ('database');

-- Tag the first post with all tags
INSERT INTO post_tags (post_id, tag_id) VALUES (1, 1);
INSERT INTO post_tags (post_id, tag_id) VALUES (1, 2);
INSERT INTO post_tags (post_id, tag_id) VALUES (1, 3);

-- Tag other posts
INSERT INTO post_tags (post_id, tag_id) VALUES (2, 1);
INSERT INTO post_tags (post_id, tag_id) VALUES (3, 2);
EOF