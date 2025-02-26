"""
Comprehensive test suite for fastmigrate.

This test is designed to be highly legible and test all aspects of fastmigrate
in a single integrated test flow, verifying:
1. Basic migration functionality
2. Rollback on failure
3. Interactive mode
4. Dry run mode
5. Version tracking
6. Detection of migration script errors
7. All supported script types (SQL, Python, Shell)

Each step is clearly documented with intermediate assertions to make it
easy to understand what's happening and what's expected.
"""

import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from fastmigrate.core import (
    ensure_meta_table, get_db_version, set_db_version,
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
        
        # Initialize the _meta table (should be version 0)
        ensure_meta_table(self.conn)
        
        # Verify we're starting with version 0
        self.assertEqual(get_db_version(self.conn), 0, 
                         "Database should start with version 0")
        
        # Close the connection - will reopen as needed in tests
        self.conn.close()
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
        
        # Step 2: Test dry run mode - should report migrations but not execute any
        print("\nSTEP 2: Test dry run mode")
        success = run_migrations(self.db_path, self.migrations_dir, dry_run=True)
        
        # The dry run should succeed
        self.assertTrue(success, "Dry run should succeed")
        
        # Open a connection and check the version - should still be 0
        self.conn = sqlite3.connect(self.db_path)
        db_version = get_db_version(self.conn)
        self.assertEqual(db_version, 0, 
                         "After dry run, DB version should still be 0")
        
        # Check that the users table doesn't exist yet
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        self.assertIsNone(cursor.fetchone(), 
                          "Users table should not exist after dry run")
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
        db_version = get_db_version(self.conn)
        
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
        
        # Verify tables from failed migrations don't exist
        failed_tables = ['tags', 'categories', 'tags_extended']
        for table_name in failed_tables:
            cursor = self.conn.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
            )
            self.assertIsNone(cursor.fetchone(), 
                             f"Table {table_name} should NOT exist (from failed migration)")
        
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
        -- Fixed version of migration 5
        CREATE TABLE tags (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL UNIQUE
        );
        
        -- Fixed INSERT without the missing column
        INSERT INTO tags (id, name) VALUES (1, 'sql');
        """
        with open(os.path.join(fixed_migrations_dir, "0005-fixed-sql-migration.sql"), "w") as f:
            f.write(fixed_sql)
        
        # Run migrations again with the fixed migrations
        success = run_migrations(self.db_path, fixed_migrations_dir)
        
        # This time it should succeed
        self.assertTrue(success, "Migrations should succeed with fixed SQL migration")
        
        # Verify the DB version
        self.conn = sqlite3.connect(self.db_path)
        db_version = get_db_version(self.conn)
        self.assertEqual(db_version, 5, 
                         "After running fixed migrations, DB version should be 5")
        
        # Verify the tags table was created and has data
        cursor = self.conn.execute("SELECT name FROM tags")
        tag = cursor.fetchone()
        self.assertEqual(tag[0], 'sql', 
                         "Tag should be created with correct data")
        
        # Step 5: Test interactive mode (simulate user selecting only certain migrations)
        print("\nSTEP 5: Test interactive mode")
        
        # Create more migrations for testing interactive mode
        migrations_interactive = os.path.join(self.temp_dir, "interactive_migrations")
        os.makedirs(migrations_interactive, exist_ok=True)
        
        # Create simple migrations
        for i in range(10, 13):
            sql = f"-- Migration {i}\nCREATE TABLE table_{i} (id INTEGER PRIMARY KEY);"
            with open(os.path.join(migrations_interactive, f"{i:04d}-create-table-{i}.sql"), "w") as f:
                f.write(sql)
        
        # Create a modified version of run_migrations to simulate user input
        def simulate_interactive_migrations(db_path, migrations_dir, selected_versions):
            """Simulate interactive migration with predetermined choices."""
            
            # Store the original input function
            import builtins
            original_input = builtins.input
            responses = []
            
            # Generate simulated user responses
            for version in sorted(get_migration_scripts(migrations_dir).keys()):
                if version in selected_versions:
                    responses.append("y")  # Yes to selected versions
                else:
                    responses.append("n")  # No to other versions
            
            response_index = 0
            
            def mock_input(prompt):
                nonlocal response_index
                response = responses[response_index]
                response_index += 1
                print(f"[Mock user input] {prompt} -> {response}")
                return response
            
            try:
                # Replace input with our mock version
                builtins.input = mock_input
                
                # Run migrations in interactive mode
                return run_migrations(db_path, migrations_dir, interactive=True)
            finally:
                # Restore original input function
                builtins.input = original_input
        
        # Simulate user selecting only migrations 10 and 12
        selected_versions = [10, 12]
        success = simulate_interactive_migrations(
            self.db_path, migrations_interactive, selected_versions
        )
        
        # Verify it succeeded
        self.assertTrue(success, "Interactive migrations should succeed")
        
        # Verify only selected migrations were applied
        self.conn = sqlite3.connect(self.db_path)
        
        # DB version should be the highest selected version
        db_version = get_db_version(self.conn)
        self.assertEqual(db_version, 12, 
                         "DB version should be set to highest applied migration (12)")
        
        # Check that tables 10 and 12 exist (selected)
        for version in selected_versions:
            cursor = self.conn.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='table_{version}'"
            )
            self.assertIsNotNone(cursor.fetchone(), 
                                f"Table table_{version} should exist (selected in interactive mode)")
        
        # Check that table 11 doesn't exist (not selected)
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='table_11'"
        )
        self.assertIsNone(cursor.fetchone(), 
                          "Table table_11 should NOT exist (skipped in interactive mode)")
        
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