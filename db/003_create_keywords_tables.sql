-- Radar TRH keyword processing schema
--
-- Supports a versioned canonical dictionary, per-news extracted keywords, and
-- monthly aggregates used by the Radar agenda UI.

CREATE TABLE IF NOT EXISTS radar_keyword_dictionary (
    id BIGSERIAL PRIMARY KEY,
    canonical_keyword TEXT NOT NULL UNIQUE,
    normalized_keyword TEXT NOT NULL UNIQUE,
    keyword_type VARCHAR(40) NOT NULL DEFAULT 'topic',
    category VARCHAR(80),
    priority INTEGER NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    source VARCHAR(40) NOT NULL DEFAULT 'config',
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_radar_keyword_dictionary_enabled
    ON radar_keyword_dictionary (enabled);

CREATE INDEX IF NOT EXISTS idx_radar_keyword_dictionary_type
    ON radar_keyword_dictionary (keyword_type);

CREATE TABLE IF NOT EXISTS radar_keyword_aliases (
    id BIGSERIAL PRIMARY KEY,
    keyword_id BIGINT NOT NULL REFERENCES radar_keyword_dictionary(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL UNIQUE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_radar_keyword_aliases_keyword
    ON radar_keyword_aliases (keyword_id);

CREATE INDEX IF NOT EXISTS idx_radar_keyword_aliases_enabled
    ON radar_keyword_aliases (enabled);

CREATE TABLE IF NOT EXISTS radar_news_keywords (
    id BIGSERIAL PRIMARY KEY,
    raw_noticia_id BIGINT NOT NULL REFERENCES radar_raw_noticias(id) ON DELETE CASCADE,
    noticia_hash VARCHAR(64) NOT NULL,
    month_start DATE NOT NULL,
    keyword TEXT NOT NULL,
    normalized_keyword TEXT NOT NULL,
    canonical_keyword TEXT,
    normalized_canonical_keyword TEXT,
    keyword_type VARCHAR(40),
    extractor_source VARCHAR(20) NOT NULL CHECK (extractor_source IN ('dictionary', 'spacy', 'yake')),
    score NUMERIC(12, 6),
    occurrences INTEGER NOT NULL DEFAULT 1,
    source_media VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (raw_noticia_id, normalized_keyword, extractor_source)
);

CREATE INDEX IF NOT EXISTS idx_radar_news_keywords_month
    ON radar_news_keywords (month_start);

CREATE INDEX IF NOT EXISTS idx_radar_news_keywords_normalized
    ON radar_news_keywords (normalized_keyword);

CREATE INDEX IF NOT EXISTS idx_radar_news_keywords_canonical
    ON radar_news_keywords (normalized_canonical_keyword);

CREATE INDEX IF NOT EXISTS idx_radar_news_keywords_source
    ON radar_news_keywords (extractor_source);

CREATE INDEX IF NOT EXISTS idx_radar_news_keywords_media
    ON radar_news_keywords (source_media);

CREATE TABLE IF NOT EXISTS radar_monthly_keyword_stats (
    id BIGSERIAL PRIMARY KEY,
    month_start DATE NOT NULL,
    keyword TEXT NOT NULL,
    normalized_keyword TEXT NOT NULL,
    canonical_keyword TEXT,
    normalized_canonical_keyword TEXT,
    keyword_type VARCHAR(40),
    extractor_sources TEXT[] NOT NULL DEFAULT '{}',
    news_count INTEGER NOT NULL DEFAULT 0,
    total_occurrences INTEGER NOT NULL DEFAULT 0,
    avg_score NUMERIC(12, 6),
    source_media_count INTEGER NOT NULL DEFAULT 0,
    source_media_stats JSONB NOT NULL DEFAULT '{}'::jsonb,
    priority INTEGER NOT NULL DEFAULT 0,
    updated_from_run_id BIGINT REFERENCES radar_processing_runs(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (month_start, normalized_keyword)
);

CREATE INDEX IF NOT EXISTS idx_radar_monthly_keyword_stats_month
    ON radar_monthly_keyword_stats (month_start);

CREATE INDEX IF NOT EXISTS idx_radar_monthly_keyword_stats_rank
    ON radar_monthly_keyword_stats (month_start, priority DESC, news_count DESC, total_occurrences DESC);

CREATE INDEX IF NOT EXISTS idx_radar_monthly_keyword_stats_canonical
    ON radar_monthly_keyword_stats (normalized_canonical_keyword);

CREATE OR REPLACE FUNCTION set_radar_keywords_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_radar_keyword_dictionary_updated_at ON radar_keyword_dictionary;
CREATE TRIGGER trg_radar_keyword_dictionary_updated_at
BEFORE UPDATE ON radar_keyword_dictionary
FOR EACH ROW
EXECUTE FUNCTION set_radar_keywords_updated_at();

DROP TRIGGER IF EXISTS trg_radar_keyword_aliases_updated_at ON radar_keyword_aliases;
CREATE TRIGGER trg_radar_keyword_aliases_updated_at
BEFORE UPDATE ON radar_keyword_aliases
FOR EACH ROW
EXECUTE FUNCTION set_radar_keywords_updated_at();

DROP TRIGGER IF EXISTS trg_radar_news_keywords_updated_at ON radar_news_keywords;
CREATE TRIGGER trg_radar_news_keywords_updated_at
BEFORE UPDATE ON radar_news_keywords
FOR EACH ROW
EXECUTE FUNCTION set_radar_keywords_updated_at();

DROP TRIGGER IF EXISTS trg_radar_monthly_keyword_stats_updated_at ON radar_monthly_keyword_stats;
CREATE TRIGGER trg_radar_monthly_keyword_stats_updated_at
BEFORE UPDATE ON radar_monthly_keyword_stats
FOR EACH ROW
EXECUTE FUNCTION set_radar_keywords_updated_at();
