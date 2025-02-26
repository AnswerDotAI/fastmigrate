-- First statement is valid and will execute
INSERT INTO test_table (name) VALUES ('this_will_be_inserted');

-- This has a syntax error and will cause the script to fail
CREATE TABLE this_syntax_error (
  id INTEGER PRIMARY
  name TEXT -- Missing comma after PRIMARY
);