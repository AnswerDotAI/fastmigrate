-- Initial schema setup
CREATE TABLE migrations_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    migration_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    execution_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Record that this migration was executed
INSERT INTO migrations_log (migration_id, description) 
VALUES (1, 'Initial schema created');