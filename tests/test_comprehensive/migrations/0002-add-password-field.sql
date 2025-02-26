-- Add password field to users table
ALTER TABLE users ADD COLUMN password_hash TEXT;

-- Update existing users with default password
UPDATE users SET password_hash = 'default_hash_placeholder';