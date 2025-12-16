-- Migration to convert ctime and mtime from Integer to TIMESTAMP for accounts table
-- This migration handles the conversion of existing integer timestamps to TIMESTAMP format

-- Step 1: Add new temporary columns with TIMESTAMP type
ALTER TABLE accounts ADD COLUMN ctime_new TIMESTAMP;
ALTER TABLE accounts ADD COLUMN mtime_new TIMESTAMP;

-- Step 2: Convert existing integer timestamps to TIMESTAMP
-- Convert Unix timestamp integers to TIMESTAMP format
UPDATE accounts 
SET ctime_new = to_timestamp(ctime) 
WHERE ctime IS NOT NULL;

UPDATE accounts 
SET mtime_new = to_timestamp(mtime) 
WHERE mtime IS NOT NULL;

-- Step 3: Handle any NULL values by setting them to current timestamp
UPDATE accounts 
SET ctime_new = CURRENT_TIMESTAMP 
WHERE ctime_new IS NULL;

UPDATE accounts 
SET mtime_new = CURRENT_TIMESTAMP 
WHERE mtime_new IS NULL;

-- Step 4: Drop the old integer columns
ALTER TABLE accounts DROP COLUMN ctime;
ALTER TABLE accounts DROP COLUMN mtime;

-- Step 5: Rename the new columns to the original names
ALTER TABLE accounts RENAME COLUMN ctime_new TO ctime;
ALTER TABLE accounts RENAME COLUMN mtime_new TO mtime;

-- Step 6: Set default values for future inserts
ALTER TABLE accounts ALTER COLUMN ctime SET DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE accounts ALTER COLUMN mtime SET DEFAULT CURRENT_TIMESTAMP;
