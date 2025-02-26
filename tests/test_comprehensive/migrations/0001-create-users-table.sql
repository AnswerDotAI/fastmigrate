-- Create the users table for tracking application users
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add sample user
INSERT INTO users (username, email) VALUES ('admin', 'admin@example.com');