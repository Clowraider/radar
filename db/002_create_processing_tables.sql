-- Radar TRH processing state schema
--
-- Tracks processing runs and monthly periods affected by newly synced raw news.
-- Sync freshness is based on `synced_at`/`fecha_extraccion`, while analytics
-- periods are based on `fecha_publicacion`.

CREATE TABLE IF NOT EXISTS radar_processing_runs (
    id BIGSERIAL PRIMARY KEY,
    run_type VARCHAR(20) NOT NULL CHECK (run_type IN ('full', 'incremental')),
    status VARCHAR(20) NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed')),
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMP,
    lookback_hours INTEGER,
    rows_detected INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_radar_processing_runs_run_type
    ON radar_processing_runs (run_type);

CREATE INDEX IF NOT EXISTS idx_radar_processing_runs_status_started
    ON radar_processing_runs (status, started_at DESC);

CREATE TABLE IF NOT EXISTS radar_affected_periods (
    id BIGSERIAL PRIMARY KEY,
    processing_run_id BIGINT REFERENCES radar_processing_runs(id) ON DELETE SET NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    month_start DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        -- 'consumed' means aggregate tables for the month have been built.
        CHECK (status IN ('pending', 'processing', 'completed', 'consumed', 'failed', 'skipped')),
    reason VARCHAR(60) NOT NULL DEFAULT 'detected',
    rows_detected INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (month_start, reason)
);

CREATE INDEX IF NOT EXISTS idx_radar_affected_periods_status_month
    ON radar_affected_periods (status, month_start);

CREATE INDEX IF NOT EXISTS idx_radar_affected_periods_run
    ON radar_affected_periods (processing_run_id);

CREATE INDEX IF NOT EXISTS idx_radar_affected_periods_month_start
    ON radar_affected_periods (month_start);

CREATE OR REPLACE FUNCTION set_radar_processing_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_radar_processing_runs_updated_at ON radar_processing_runs;
CREATE TRIGGER trg_radar_processing_runs_updated_at
BEFORE UPDATE ON radar_processing_runs
FOR EACH ROW
EXECUTE FUNCTION set_radar_processing_updated_at();

DROP TRIGGER IF EXISTS trg_radar_affected_periods_updated_at ON radar_affected_periods;
CREATE TRIGGER trg_radar_affected_periods_updated_at
BEFORE UPDATE ON radar_affected_periods
FOR EACH ROW
EXECUTE FUNCTION set_radar_processing_updated_at();
