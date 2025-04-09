"""
Comprehensive test suite for fastmigrate.

This test is designed to be highly legible and test all aspects of fastmigrate
in a single integrated test flow, verifying:
1. Basic migration functionality
2. Handling migration failures
3. Version tracking
4. Detection of migration script errors
5. All supported script types (SQL, Python, Shell)
6. Resuming migration after fixing errors

Each step is clearly documented with intermediate assertions to make it
easy to understand what's happening and what's expected.

Note: This test verifies the core functionality of fastmigrate after simplification.
Failed migrations now stop the migration process but don't roll back previous changes.
"""

import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from fastmigrate.core import (
    _ensure_meta_table, get_db_version, _set_db_version,
    get_migration_scripts, run_migrations
)


class TestComprehensiveMigrationFlow(unittest.TestCase):
    """Comprehensive test of the complete migration flow."""
    
    def setUp(self):
        """Set up a clean environment for each test."""
        # Create a temporary directory for our tests
        self.temp_dir = tempfile.mkdtemp()
        
        # Define paths for our test database and migrations
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.migrations_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            "migrations"
        )
        
        # Create an initial empty database
        self.conn = sqlite3.connect(self.db_path)
        self.conn.close()
        
        # Initialize the _meta table (should be version 0)
        _ensure_meta_table(self.db_path)
        
        # Verify we're starting with version 0
        self.assertEqual(get_db_version(self.db_path), 0, 
                         "Database should start with version 0")
        
        self.conn = None
        
    def tearDown(self):
        """Clean up after each test."""
        # Close any open connection
        if self.conn:
            self.conn.close()
        
        # Clean up the temporary directory
        shutil.rmtree(self.temp_dir)
    
    def test_comprehensive_migration_flow(self):
        """
        Run through a complex migration flow testing all features.
        
        This test is deliberately verbose and sequential to make it easy to
        understand what is being tested.
        """
        print("\n--- Starting Comprehensive Test Suite ---")
        
        # Step 1: Verify we have our migration scripts
        print("\nSTEP 1: Verify migration script detection")
        scripts = get_migration_scripts(self.migrations_dir)
        print(f"Found {len(scripts)} migration scripts")
        
        # We should have all our prepared migrations available (7 scripts)
        self.assertEqual(len(scripts), 7, 
                         "Should find 7 migration scripts in test directory")
        
        # The keys should be the version numbers in our migration filenames
        versions = sorted(scripts.keys())
        expected_versions = [1, 2, 3, 4, 5, 6, 7]
        self.assertEqual(versions, expected_versions, 
                         "Migration versions should match expected sequence")
        
        # Directly check the database state before running migrations
        print("\nSTEP 2: Check initial database state")
        self.conn = sqlite3.connect(self.db_path)
        db_version = get_db_version(self.db_path)
        self.assertEqual(db_version, 0, 
                         "Initial DB version should be 0")
        
        # Check that the users table doesn't exist yet
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        self.assertIsNone(cursor.fetchone(), 
                          "Users table should not exist in initial state")
        self.conn.close()
        
        # Step 3: Run the first 4 migrations (these should all succeed)
        print("\nSTEP 3: Run successful migrations 1-4")
        # Create a connection to run migrations
        success = run_migrations(self.db_path, self.migrations_dir)
        
        # The migrations should fail at migration 5 (bad SQL), so we check for failure
        self.assertFalse(success, 
                         "Migrations should fail when it hits the bad SQL migration")
        
        # Open a connection and verify where we ended up
        self.conn = sqlite3.connect(self.db_path)
        db_version = get_db_version(self.db_path)
        
        # We should have successfully applied migrations 1-4
        self.assertEqual(db_version, 4, 
                         "After running migrations, DB version should be 4")
        
        # Verify the tables from migrations 1-4 were created
        tables = {
            'users': "Created by migration 0001",
            'posts': "Created by migration 0003",
            'comments': "Created by migration 0004"
        }
        
        # Check each table exists
        for table_name, description in tables.items():
            cursor = self.conn.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
            )
            self.assertIsNotNone(cursor.fetchone(), 
                                f"Table {table_name} should exist ({description})")
        
        # Verify the password_hash column was added to users
        cursor = self.conn.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        self.assertIn("password_hash", columns, 
                      "password_hash column should exist in users table (from migration 0002)")
        
        # Verify data was properly inserted
        # Check user record
        cursor = self.conn.execute("SELECT username, email FROM users")
        user = cursor.fetchone()
        self.assertEqual(user, ('admin', 'admin@example.com'), 
                         "Admin user should be created with correct data")
        
        # Check post record
        cursor = self.conn.execute("SELECT title, content FROM posts")
        post = cursor.fetchone()
        self.assertEqual(post, ('First Post', 'Hello World!'), 
                         "Sample post should be created with correct data")
        
        # Check comment record
        cursor = self.conn.execute("SELECT content FROM comments")
        comment = cursor.fetchone()
        self.assertEqual(comment[0], 'Great first post!', 
                         "Sample comment should be created with correct data")
        
        # Without rollbacks, some tables might get created before errors in SQL scripts
        # So we just check that the later steps in the failing migrations didn't execute
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='categories'"
        )
        self.assertIsNone(cursor.fetchone(),
                         "Categories table should NOT exist (from later failed migration)")
        
        # Step 4: Fix the bad SQL migration and re-run
        print("\nSTEP 4: Fix bad SQL migration and re-run")
        # Create a fixed migration file in the temporary directory
        fixed_migrations_dir = os.path.join(self.temp_dir, "fixed_migrations")
        os.makedirs(fixed_migrations_dir, exist_ok=True)
        
        # Copy over the first 4 successful migrations
        for i in range(1, 5):
            for ext in ['.sql', '.py', '.sh']:
                src = os.path.join(self.migrations_dir, f"{i:04d}-{self._get_migration_name(i)}{ext}")
                if os.path.exists(src):
                    shutil.copy(src, fixed_migrations_dir)
        
        # Create fixed version of migration 5 (with correct SQL)
        fixed_sql = """
        -- Fixed version of migration 5 (with IF NOT EXISTS because table might already exist)
        CREATE TABLE IF NOT EXISTS tags (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL UNIQUE
        );
        
        -- Fixed INSERT without the missing column (using OR REPLACE for safety)
        INSERT OR REPLACE INTO tags (id, name) VALUES (1, 'sql');
        """
        with open(os.path.join(fixed_migrations_dir, "0005-fixed-sql-migration.sql"), "w") as f:
            f.write(fixed_sql)
        
        # Run migrations again with the fixed migrations
        success = run_migrations(self.db_path, fixed_migrations_dir)
        
        # This time it should succeed
        self.assertTrue(success, "Migrations should succeed with fixed SQL migration")
        
        # Verify the DB version
        self.conn = sqlite3.connect(self.db_path)
        db_version = get_db_version(self.db_path)
        self.assertEqual(db_version, 5, 
                         "After running fixed migrations, DB version should be 5")
        
        # Verify the tags table was created and has data
        cursor = self.conn.execute("SELECT name FROM tags")
        tag = cursor.fetchone()
        self.assertEqual(tag[0], 'sql', 
                         "Tag should be created with correct data")
        
        
        print("\n--- Comprehensive Test Suite Completed Successfully ---")
    
    def _get_migration_name(self, version):
        """Helper method to get migration names for easier script generation."""
        mapping = {
            1: "create-users-table",
            2: "add-password-field",
            3: "add-posts-table",
            4: "create-comments",
            5: "bad-sql-migration",
            6: "bad-python-migration",
            7: "bad-shell-migration",
        }
        return mapping.get(version, f"migration-{version}")


if __name__ == '__main__':
    unittest.main()