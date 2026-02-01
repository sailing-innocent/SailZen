-- Migration to fix transactions table sequence
-- This migration fixes the sequence for the transactions.id column
-- Date: 2026-01-27
-- 
-- Problem:
-- When data is inserted directly (not through SQLAlchemy ORM), the PostgreSQL
-- sequence may not be updated, causing duplicate key violations.
--
-- Solution:
-- Reset the sequence to the maximum id value + 1
--
-- Execution:
-- Option 1 (Python, recommended): python sail_server/migration/run_fix_transactions_sequence.py
-- Option 2 (psql): \i sail_server/migration/fix_transactions_sequence.sql

-- Step 1: Find the sequence name for transactions.id
-- PostgreSQL typically creates sequences named: tablename_columnname_seq
DO $$
DECLARE
    seq_name TEXT;
    max_id INTEGER;
    new_seq_value INTEGER;
BEGIN
    -- Get the sequence name
    SELECT pg_get_serial_sequence('transactions', 'id') INTO seq_name;
    
    IF seq_name IS NULL THEN
        RAISE NOTICE 'No sequence found for transactions.id. Creating one...';
        -- Create sequence if it doesn't exist
        CREATE SEQUENCE IF NOT EXISTS transactions_id_seq OWNED BY transactions.id;
        seq_name := 'transactions_id_seq';
    END IF;
    
    RAISE NOTICE 'Found sequence: %', seq_name;
    
    -- Get the maximum id from the table
    SELECT COALESCE(MAX(id), 0) INTO max_id FROM transactions;
    RAISE NOTICE 'Current maximum id in transactions table: %', max_id;
    
    -- Set the sequence to max_id + 1
    new_seq_value := max_id + 1;
    EXECUTE format('SELECT setval(%L, %s, false)', seq_name, new_seq_value);
    
    RAISE NOTICE 'Sequence % set to %', seq_name, new_seq_value;
    
    -- Verify the sequence value
    EXECUTE format('SELECT last_value FROM %I', seq_name) INTO new_seq_value;
    RAISE NOTICE 'Verified sequence value: %', new_seq_value;
END $$;

-- Step 2: Ensure the sequence is owned by the column (for safety)
DO $$
DECLARE
    seq_name TEXT;
BEGIN
    SELECT pg_get_serial_sequence('transactions', 'id') INTO seq_name;
    IF seq_name IS NOT NULL THEN
        -- Make sure the sequence is owned by the column
        EXECUTE format('ALTER SEQUENCE %I OWNED BY transactions.id', seq_name);
        RAISE NOTICE 'Sequence ownership verified';
    END IF;
END $$;

-- Verification query (uncomment to run):
-- SELECT pg_get_serial_sequence('transactions', 'id') AS sequence_name;
-- SELECT last_value FROM transactions_id_seq;
-- SELECT MAX(id) FROM transactions;

-- Notes:
-- - This migration is idempotent and can be run multiple times safely
-- - The sequence will be set to MAX(id) + 1, ensuring no conflicts
-- - If the table is empty, the sequence will be set to 1
