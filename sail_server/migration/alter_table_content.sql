-- Migration to convert ctime and mtime from Integer to TIMESTAMP for content tables
-- This migration handles the conversion of existing integer timestamps to TIMESTAMP format
-- Affected tables: chapter, vault_note

-- ============================================
-- Chapter table migration
-- ============================================

-- Step 1: Add new temporary columns with TIMESTAMP type for chapter table
ALTER TABLE chapter ADD COLUMN ctime_new TIMESTAMP;
ALTER TABLE chapter ADD COLUMN mtime_new TIMESTAMP;

-- Step 2: Convert existing integer timestamps to TIMESTAMP for chapter table
UPDATE chapter 
SET ctime_new = to_timestamp(ctime) 
WHERE ctime IS NOT NULL;

UPDATE chapter 
SET mtime_new = to_timestamp(mtime) 
WHERE mtime IS NOT NULL;

-- Step 3: Handle any NULL values by setting them to current timestamp for chapter table
UPDATE chapter 
SET ctime_new = CURRENT_TIMESTAMP 
WHERE ctime_new IS NULL;

UPDATE chapter 
SET mtime_new = CURRENT_TIMESTAMP 
WHERE mtime_new IS NULL;

-- Step 4: Drop the old integer columns for chapter table
ALTER TABLE chapter DROP COLUMN ctime;
ALTER TABLE chapter DROP COLUMN mtime;

-- Step 5: Rename the new columns to the original names for chapter table
ALTER TABLE chapter RENAME COLUMN ctime_new TO ctime;
ALTER TABLE chapter RENAME COLUMN mtime_new TO mtime;

-- Step 6: Set default values for future inserts for chapter table
ALTER TABLE chapter ALTER COLUMN ctime SET DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE chapter ALTER COLUMN mtime SET DEFAULT CURRENT_TIMESTAMP;

-- ============================================
-- Vault Note table migration
-- ============================================

-- Step 1: Add new temporary columns with TIMESTAMP type for vault_note table
ALTER TABLE vault_note ADD COLUMN ctime_new TIMESTAMP;
ALTER TABLE vault_note ADD COLUMN mtime_new TIMESTAMP;

-- Step 2: Convert existing integer timestamps to TIMESTAMP for vault_note table
UPDATE vault_note 
SET ctime_new = to_timestamp(ctime) 
WHERE ctime IS NOT NULL;

UPDATE vault_note 
SET mtime_new = to_timestamp(mtime) 
WHERE mtime IS NOT NULL;

-- Step 3: Handle any NULL values by setting them to current timestamp for vault_note table
UPDATE vault_note 
SET ctime_new = CURRENT_TIMESTAMP 
WHERE ctime_new IS NULL;

UPDATE vault_note 
SET mtime_new = CURRENT_TIMESTAMP 
WHERE mtime_new IS NULL;

-- Step 4: Drop the old integer columns for vault_note table
ALTER TABLE vault_note DROP COLUMN ctime;
ALTER TABLE vault_note DROP COLUMN mtime;

-- Step 5: Rename the new columns to the original names for vault_note table
ALTER TABLE vault_note RENAME COLUMN ctime_new TO ctime;
ALTER TABLE vault_note RENAME COLUMN mtime_new TO mtime;

-- Step 6: Set default values for future inserts for vault_note table
ALTER TABLE vault_note ALTER COLUMN ctime SET DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE vault_note ALTER COLUMN mtime SET DEFAULT CURRENT_TIMESTAMP;
