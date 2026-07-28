-- Migration: allow 'consumed' status in radar_affected_periods.
--
-- `consumed` means aggregate tables for the month have been built.
-- This is applied idempotently so it can run on both existing databases
-- (which may have the old CHECK constraint without 'consumed') and new ones.

ALTER TABLE radar_affected_periods
DROP CONSTRAINT IF EXISTS radar_affected_periods_status_check;

ALTER TABLE radar_affected_periods
ADD CONSTRAINT radar_affected_periods_status_check
CHECK (status IN ('pending', 'processing', 'completed', 'consumed', 'failed', 'skipped'));
