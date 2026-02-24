-- Migration: Convert Project start_time/end_time to QBW format
-- Description: 
--   1. Add new columns start_time_qbw/end_time_qbw
--   2. Convert existing Unix timestamp values to QBW format (YYYYQQWW)
--   3. Copy existing QBW format values
--   4. Set default values for NULL entries
--   5. Make new columns NOT NULL
--   6. Drop old columns start_time/end_time

-- Step 1: Add new columns
ALTER TABLE projects ADD COLUMN IF NOT EXISTS start_time_qbw INTEGER;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS end_time_qbw INTEGER;

-- Step 2: Update existing data - Convert Unix timestamp to QBW format
-- QBW format: YYYY * 100 + Quarter * 10 + BiWeekIndex
-- For Unix timestamps, we convert to date first, then calculate QBW

UPDATE projects 
SET 
    start_time_qbw = (
        -- Extract year, quarter, and approximate biweek from Unix timestamp
        (EXTRACT(YEAR FROM TO_TIMESTAMP(start_time))::INTEGER * 100) +
        ((EXTRACT(MONTH FROM TO_TIMESTAMP(start_time))::INTEGER - 1) / 3 + 1) * 10 +
        -- Approximate biweek (1-6) based on day of quarter
        LEAST(
            ((EXTRACT(DOY FROM TO_TIMESTAMP(start_time))::INTEGER - 
              ((EXTRACT(MONTH FROM TO_TIMESTAMP(start_time))::INTEGER - 1) / 3) * 91
            ) / 14) + 1,
            6
        )
    ),
    end_time_qbw = (
        (EXTRACT(YEAR FROM TO_TIMESTAMP(end_time))::INTEGER * 100) +
        ((EXTRACT(MONTH FROM TO_TIMESTAMP(end_time))::INTEGER - 1) / 3 + 1) * 10 +
        LEAST(
            ((EXTRACT(DOY FROM TO_TIMESTAMP(end_time))::INTEGER - 
              ((EXTRACT(MONTH FROM TO_TIMESTAMP(end_time))::INTEGER - 1) / 3) * 91
            ) / 14) + 1,
            6
        )
    )
WHERE start_time > 1000000000;  -- Only convert Unix timestamps (after year 2001)

-- Step 3: For values that are already in QBW format (6 digits like 202616), just copy them
UPDATE projects 
SET 
    start_time_qbw = start_time,
    end_time_qbw = end_time
WHERE start_time BETWEEN 200000 AND 209999;  -- QBW format range

-- Step 4: Set default values for any NULL entries
UPDATE projects 
SET start_time_qbw = 202611  -- Default to 2026 Q1 BiWeek 1
WHERE start_time_qbw IS NULL;

UPDATE projects 
SET end_time_qbw = 202616  -- Default to 2026 Q1 BiWeek 6
WHERE end_time_qbw IS NULL;

-- Step 5: Make new columns NOT NULL
ALTER TABLE projects ALTER COLUMN start_time_qbw SET NOT NULL;
ALTER TABLE projects ALTER COLUMN end_time_qbw SET NOT NULL;

-- Step 6: Drop old columns
ALTER TABLE projects DROP COLUMN IF EXISTS start_time;
ALTER TABLE projects DROP COLUMN IF EXISTS end_time;

-- Verification query
SELECT 
    id,
    name,
    start_time_qbw,
    end_time_qbw
FROM projects
ORDER BY id;
