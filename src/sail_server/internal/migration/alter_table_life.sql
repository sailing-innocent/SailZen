-- Migration to convert ctime and mtime from BigInteger to TIMESTAMP for life tables
-- This migration handles the conversion of existing integer timestamps to TIMESTAMP format
-- Affected table: projects

-- ============================================
-- Projects table migration
-- ============================================

-- Step 1: Add new temporary columns with TIMESTAMP type for projects table
ALTER TABLE projects ADD COLUMN ctime_new TIMESTAMP;
ALTER TABLE projects ADD COLUMN mtime_new TIMESTAMP;

-- Step 2: Convert existing integer timestamps to TIMESTAMP for projects table
-- Note: BigInteger timestamps are typically in seconds, same as regular integers
UPDATE projects 
SET ctime_new = to_timestamp(ctime) 
WHERE ctime IS NOT NULL;

UPDATE projects 
SET mtime_new = to_timestamp(mtime) 
WHERE mtime IS NOT NULL;

-- Step 3: Handle any NULL values by setting them to current timestamp for projects table
UPDATE projects 
SET ctime_new = CURRENT_TIMESTAMP 
WHERE ctime_new IS NULL;

UPDATE projects 
SET mtime_new = CURRENT_TIMESTAMP 
WHERE mtime_new IS NULL;

-- Step 4: Drop the old BigInteger columns for projects table
ALTER TABLE projects DROP COLUMN ctime;
ALTER TABLE projects DROP COLUMN mtime;

-- Step 5: Rename the new columns to the original names for projects table
ALTER TABLE projects RENAME COLUMN ctime_new TO ctime;
ALTER TABLE projects RENAME COLUMN mtime_new TO mtime;

-- Step 6: Set default values for future inserts for projects table
ALTER TABLE projects ALTER COLUMN ctime SET DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE projects ALTER COLUMN mtime SET DEFAULT CURRENT_TIMESTAMP;
