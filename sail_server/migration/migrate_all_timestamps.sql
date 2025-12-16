-- Comprehensive migration script to convert all ctime/mtime fields from Integer/BigInteger to TIMESTAMP
-- This script combines all timestamp migrations for easy execution
-- 
-- Execution order:
-- 1. transactions (already exists in alter_table_transaction.sql)
-- 2. accounts
-- 3. content tables (chapter, vault_note)
-- 4. life tables (projects)

-- ============================================
-- TRANSACTIONS TABLE (Reference - already migrated)
-- ============================================
-- This section is commented out as it should already be executed
-- See alter_table_transaction.sql for details

-- ============================================
-- ACCOUNTS TABLE
-- ============================================

-- Step 1: Add new temporary columns with TIMESTAMP type for accounts table
ALTER TABLE accounts ADD COLUMN ctime_new TIMESTAMP;
ALTER TABLE accounts ADD COLUMN mtime_new TIMESTAMP;

-- Step 2: Convert existing integer timestamps to TIMESTAMP for accounts table
UPDATE accounts 
SET ctime_new = to_timestamp(ctime) 
WHERE ctime IS NOT NULL;

UPDATE accounts 
SET mtime_new = to_timestamp(mtime) 
WHERE mtime IS NOT NULL;

-- Step 3: Handle any NULL values by setting them to current timestamp for accounts table
UPDATE accounts 
SET ctime_new = CURRENT_TIMESTAMP 
WHERE ctime_new IS NULL;

UPDATE accounts 
SET mtime_new = CURRENT_TIMESTAMP 
WHERE mtime_new IS NULL;

-- Step 4: Drop the old integer columns for accounts table
ALTER TABLE accounts DROP COLUMN ctime;
ALTER TABLE accounts DROP COLUMN mtime;

-- Step 5: Rename the new columns to the original names for accounts table
ALTER TABLE accounts RENAME COLUMN ctime_new TO ctime;
ALTER TABLE accounts RENAME COLUMN mtime_new TO mtime;

-- Step 6: Set default values for future inserts for accounts table
ALTER TABLE accounts ALTER COLUMN ctime SET DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE accounts ALTER COLUMN mtime SET DEFAULT CURRENT_TIMESTAMP;

-- ============================================
-- CONTENT TABLES (Chapter and Vault Note)
-- ============================================

-- Chapter table migration
ALTER TABLE chapter ADD COLUMN ctime_new TIMESTAMP;
ALTER TABLE chapter ADD COLUMN mtime_new TIMESTAMP;

UPDATE chapter 
SET ctime_new = to_timestamp(ctime) 
WHERE ctime IS NOT NULL;

UPDATE chapter 
SET mtime_new = to_timestamp(mtime) 
WHERE mtime IS NOT NULL;

UPDATE chapter 
SET ctime_new = CURRENT_TIMESTAMP 
WHERE ctime_new IS NULL;

UPDATE chapter 
SET mtime_new = CURRENT_TIMESTAMP 
WHERE mtime_new IS NULL;

ALTER TABLE chapter DROP COLUMN ctime;
ALTER TABLE chapter DROP COLUMN mtime;

ALTER TABLE chapter RENAME COLUMN ctime_new TO ctime;
ALTER TABLE chapter RENAME COLUMN mtime_new TO mtime;

ALTER TABLE chapter ALTER COLUMN ctime SET DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE chapter ALTER COLUMN mtime SET DEFAULT CURRENT_TIMESTAMP;

-- Vault Note table migration
ALTER TABLE vault_note ADD COLUMN ctime_new TIMESTAMP;
ALTER TABLE vault_note ADD COLUMN mtime_new TIMESTAMP;

UPDATE vault_note 
SET ctime_new = to_timestamp(ctime) 
WHERE ctime IS NOT NULL;

UPDATE vault_note 
SET mtime_new = to_timestamp(mtime) 
WHERE mtime IS NOT NULL;

UPDATE vault_note 
SET ctime_new = CURRENT_TIMESTAMP 
WHERE ctime_new IS NULL;

UPDATE vault_note 
SET mtime_new = CURRENT_TIMESTAMP 
WHERE mtime_new IS NULL;

ALTER TABLE vault_note DROP COLUMN ctime;
ALTER TABLE vault_note DROP COLUMN mtime;

ALTER TABLE vault_note RENAME COLUMN ctime_new TO ctime;
ALTER TABLE vault_note RENAME COLUMN mtime_new TO mtime;

ALTER TABLE vault_note ALTER COLUMN ctime SET DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE vault_note ALTER COLUMN mtime SET DEFAULT CURRENT_TIMESTAMP;

-- ============================================
-- LIFE TABLES (Projects)
-- ============================================

-- Projects table migration
ALTER TABLE projects ADD COLUMN ctime_new TIMESTAMP;
ALTER TABLE projects ADD COLUMN mtime_new TIMESTAMP;

UPDATE projects 
SET ctime_new = to_timestamp(ctime) 
WHERE ctime IS NOT NULL;

UPDATE projects 
SET mtime_new = to_timestamp(mtime) 
WHERE mtime IS NOT NULL;

UPDATE projects 
SET ctime_new = CURRENT_TIMESTAMP 
WHERE ctime_new IS NULL;

UPDATE projects 
SET mtime_new = CURRENT_TIMESTAMP 
WHERE mtime_new IS NULL;

ALTER TABLE projects DROP COLUMN ctime;
ALTER TABLE projects DROP COLUMN mtime;

ALTER TABLE projects RENAME COLUMN ctime_new TO ctime;
ALTER TABLE projects RENAME COLUMN mtime_new TO mtime;

ALTER TABLE projects ALTER COLUMN ctime SET DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE projects ALTER COLUMN mtime SET DEFAULT CURRENT_TIMESTAMP;

-- ============================================
-- MIGRATION COMPLETE
-- ============================================
-- All ctime/mtime fields have been successfully converted to TIMESTAMP type
-- with proper default values set for future inserts
