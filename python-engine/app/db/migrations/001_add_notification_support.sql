-- Migration 001: Add notification support — Issue #56
-- Adds notification_enabled to customers and creates notification_logs table.
--
-- This migration is idempotent (safe to run multiple times).

-- 1. Add notification_enabled column to customers
ALTER TABLE customers
  ADD COLUMN IF NOT EXISTS notification_enabled BOOLEAN NOT NULL DEFAULT TRUE;

-- 2. Create notification_logs table
CREATE TABLE IF NOT EXISTS notification_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    job_id VARCHAR(50) NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    message_text TEXT,
    was_delivered BOOLEAN NOT NULL DEFAULT FALSE,
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Indexes for anti-spam queries and job tracking
CREATE INDEX IF NOT EXISTS idx_notif_customer_sent
    ON notification_logs (customer_id, sent_at);
CREATE INDEX IF NOT EXISTS idx_notif_job_id
    ON notification_logs (job_id);


-- ============================================================
-- ROLLBACK (run manually if needed):
-- ============================================================
-- DROP INDEX IF EXISTS idx_notif_job_id;
-- DROP INDEX IF EXISTS idx_notif_customer_sent;
-- DROP TABLE IF EXISTS notification_logs;
-- ALTER TABLE customers DROP COLUMN IF EXISTS notification_enabled;
