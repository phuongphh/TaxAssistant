-- Migration 002: Add tax_period and has_employees columns to customers table
-- Issue #58: Onboarding Flow Enhancement — Thu thập Tax Period
--
-- These fields are collected during onboarding step 2 to enable
-- personalized deadline calculations.

-- Forward migration
ALTER TABLE customers
  ADD COLUMN IF NOT EXISTS tax_period VARCHAR(20) DEFAULT NULL;

ALTER TABLE customers
  ADD COLUMN IF NOT EXISTS has_employees BOOLEAN DEFAULT NULL;

-- Add index for tax_period to support deadline calculator queries
CREATE INDEX IF NOT EXISTS idx_customers_tax_period ON customers (tax_period)
  WHERE tax_period IS NOT NULL;

-- Rollback:
-- DROP INDEX IF EXISTS idx_customers_tax_period;
-- ALTER TABLE customers DROP COLUMN IF EXISTS has_employees;
-- ALTER TABLE customers DROP COLUMN IF EXISTS tax_period;
