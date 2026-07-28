-- Radar TRH monthly MVP aggregate schema
--
-- These are internal DB aggregates. They keep real source/media names because
-- source anonymization is a UI/API presentation concern, not a storage concern.
-- The future UI/API should map source names to aliases such as "Fuente 1" only
-- when rendering user-facing output.

CREATE TABLE IF NOT EXISTS radar_monthly_overview (
    month_start DATE PRIMARY KEY,
    total_news INTEGER NOT NULL DEFAULT 0,
    news_with_keywords INTEGER NOT NULL DEFAULT 0,
    active_source_count INTEGER NOT NULL DEFAULT 0,
    keyword_count INTEGER NOT NULL DEFAULT 0,
    top_keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_stats JSONB NOT NULL DEFAULT '[]'::jsonb,
    first_publication_at TIMESTAMP,
    last_publication_at TIMESTAMP,
    updated_from_run_id BIGINT REFERENCES radar_processing_runs(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_radar_monthly_overview_total_news
    ON radar_monthly_overview (total_news DESC);

CREATE TABLE IF NOT EXISTS radar_daily_activity (
    id BIGSERIAL PRIMARY KEY,
    month_start DATE NOT NULL,
    activity_date DATE NOT NULL,
    news_count INTEGER NOT NULL DEFAULT 0,
    updated_from_run_id BIGINT REFERENCES radar_processing_runs(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (month_start, activity_date)
);

CREATE INDEX IF NOT EXISTS idx_radar_daily_activity_month
    ON radar_daily_activity (month_start, activity_date);

CREATE TABLE IF NOT EXISTS radar_source_monthly_stats (
    id BIGSERIAL PRIMARY KEY,
    month_start DATE NOT NULL,
    source_media TEXT NOT NULL,
    news_count INTEGER NOT NULL DEFAULT 0,
    keyword_rows INTEGER NOT NULL DEFAULT 0,
    distinct_keywords INTEGER NOT NULL DEFAULT 0,
    top_keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_from_run_id BIGINT REFERENCES radar_processing_runs(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (month_start, source_media)
);

CREATE INDEX IF NOT EXISTS idx_radar_source_monthly_stats_month_rank
    ON radar_source_monthly_stats (month_start, news_count DESC, source_media);

CREATE TABLE IF NOT EXISTS radar_source_keyword_stats (
    id BIGSERIAL PRIMARY KEY,
    month_start DATE NOT NULL,
    source_media TEXT NOT NULL,
    keyword TEXT NOT NULL,
    normalized_keyword TEXT NOT NULL,
    canonical_keyword TEXT,
    normalized_canonical_keyword TEXT,
    keyword_type VARCHAR(40),
    news_count INTEGER NOT NULL DEFAULT 0,
    total_occurrences INTEGER NOT NULL DEFAULT 0,
    avg_score NUMERIC(12, 6),
    updated_from_run_id BIGINT REFERENCES radar_processing_runs(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (month_start, source_media, normalized_keyword)
);

CREATE INDEX IF NOT EXISTS idx_radar_source_keyword_stats_month_rank
    ON radar_source_keyword_stats (month_start, news_count DESC, total_occurrences DESC);

CREATE INDEX IF NOT EXISTS idx_radar_source_keyword_stats_source
    ON radar_source_keyword_stats (month_start, source_media, news_count DESC);

CREATE INDEX IF NOT EXISTS idx_radar_source_keyword_stats_keyword
    ON radar_source_keyword_stats (normalized_keyword);

DROP TRIGGER IF EXISTS trg_radar_monthly_overview_updated_at ON radar_monthly_overview;
CREATE TRIGGER trg_radar_monthly_overview_updated_at
BEFORE UPDATE ON radar_monthly_overview
FOR EACH ROW
EXECUTE FUNCTION set_radar_keywords_updated_at();

DROP TRIGGER IF EXISTS trg_radar_daily_activity_updated_at ON radar_daily_activity;
CREATE TRIGGER trg_radar_daily_activity_updated_at
BEFORE UPDATE ON radar_daily_activity
FOR EACH ROW
EXECUTE FUNCTION set_radar_keywords_updated_at();

DROP TRIGGER IF EXISTS trg_radar_source_monthly_stats_updated_at ON radar_source_monthly_stats;
CREATE TRIGGER trg_radar_source_monthly_stats_updated_at
BEFORE UPDATE ON radar_source_monthly_stats
FOR EACH ROW
EXECUTE FUNCTION set_radar_keywords_updated_at();

DROP TRIGGER IF EXISTS trg_radar_source_keyword_stats_updated_at ON radar_source_keyword_stats;
CREATE TRIGGER trg_radar_source_keyword_stats_updated_at
BEFORE UPDATE ON radar_source_keyword_stats
FOR EACH ROW
EXECUTE FUNCTION set_radar_keywords_updated_at();
