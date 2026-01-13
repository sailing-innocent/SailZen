-- Migration to add budget_id column to transactions table
-- This migration adds a foreign key relationship between transactions and budgets
-- Date: 2026-01-12
-- 
-- Prerequisites:
-- 1. The budgets table must exist (created by SQLAlchemy's create_all() or manually)
-- 2. Backup your database before running this migration
--
-- Execution:
-- \i sail_server/migration/add_budget_id_to_transaction.sql
-- Or execute this file directly in psql

-- Step 1: Check if budgets table exists, if not create it
-- Note: SQLAlchemy will create it automatically, but we check here for safety
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'budgets') THEN
        RAISE NOTICE 'budgets table does not exist. It will be created by SQLAlchemy on next application start.';
    END IF;
END $$;

-- Step 2: Add budget_id column (nullable initially to allow existing transactions)
-- Check if column already exists to make migration idempotent
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'transactions' AND column_name = 'budget_id'
    ) THEN
        ALTER TABLE transactions ADD COLUMN budget_id INTEGER;
        RAISE NOTICE 'Added budget_id column to transactions table';
    ELSE
        RAISE NOTICE 'budget_id column already exists in transactions table';
    END IF;
END $$;

-- Step 3: Add foreign key constraint to budgets table
-- Check if constraint already exists to make migration idempotent
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_transaction_budget' 
        AND table_name = 'transactions'
    ) THEN
        ALTER TABLE transactions 
        ADD CONSTRAINT fk_transaction_budget 
        FOREIGN KEY (budget_id) REFERENCES budgets(id) 
        ON DELETE SET NULL;
        RAISE NOTICE 'Added foreign key constraint fk_transaction_budget';
    ELSE
        RAISE NOTICE 'Foreign key constraint fk_transaction_budget already exists';
    END IF;
END $$;

-- Step 4: Create index for better query performance
CREATE INDEX IF NOT EXISTS idx_transactions_budget_id ON transactions(budget_id);

-- Verification queries (uncomment to run):
-- SELECT column_name, data_type, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_name = 'transactions' AND column_name = 'budget_id';
--
-- SELECT constraint_name, constraint_type 
-- FROM information_schema.table_constraints 
-- WHERE table_name = 'transactions' AND constraint_name = 'fk_transaction_budget';

-- Notes: 
-- - Existing transactions will have budget_id = NULL
-- - The foreign key constraint ensures referential integrity
-- - ON DELETE SET NULL means if a budget is deleted, linked transactions will have budget_id set to NULL
-- - This migration is idempotent and can be run multiple times safely
