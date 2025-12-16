-- Migration to convert ctime and mtime from Integer to TIMESTAMP
-- This migration handles the conversion of existing integer timestamps to TIMESTAMP format

-- Step 1: Add new temporary columns with TIMESTAMP type
ALTER TABLE transactions ADD COLUMN ctime_new TIMESTAMP;
ALTER TABLE transactions ADD COLUMN mtime_new TIMESTAMP;

-- Step 2: Convert existing integer timestamps to TIMESTAMP
-- Convert Unix timestamp integers to TIMESTAMP format
UPDATE transactions 
SET ctime_new = to_timestamp(ctime) 
WHERE ctime IS NOT NULL;

UPDATE transactions 
SET mtime_new = to_timestamp(mtime) 
WHERE mtime IS NOT NULL;

-- Step 3: Handle any NULL values by setting them to current timestamp
UPDATE transactions 
SET ctime_new = CURRENT_TIMESTAMP 
WHERE ctime_new IS NULL;

UPDATE transactions 
SET mtime_new = CURRENT_TIMESTAMP 
WHERE mtime_new IS NULL;

-- Step 4: Drop the old integer columns
ALTER TABLE transactions DROP COLUMN ctime;
ALTER TABLE transactions DROP COLUMN mtime;

-- Step 5: Rename the new columns to the original names
ALTER TABLE transactions RENAME COLUMN ctime_new TO ctime;
ALTER TABLE transactions RENAME COLUMN mtime_new TO mtime;

-- Step 6: Set default values for future inserts
ALTER TABLE transactions ALTER COLUMN ctime SET DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE transactions ALTER COLUMN mtime SET DEFAULT CURRENT_TIMESTAMP;
