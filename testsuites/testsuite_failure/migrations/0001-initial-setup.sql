-- Initial setup that succeeds
CREATE TABLE test_table (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

-- Add some sample data
INSERT INTO test_table (name) VALUES ('test1');
INSERT INTO test_table (name) VALUES ('test2');