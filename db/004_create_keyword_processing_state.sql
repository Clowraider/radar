-- Radar TRH per-news keyword processing state
--
-- Required for long-running, interruptible keyword extraction. A news item can
-- be processed and produce zero keyword rows, so resume logic must not rely on
-- radar_news_keywords existence alone.

CREATE TABLE IF NOT EXISTS radar_news_keyword_processing (
    raw_noticia_id BIGINT PRIMARY KEY REFERENCES radar_raw_noticias(id) ON DELETE CASCADE,
    month_start DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'completed'
        CHECK (status IN ('completed', 'failed')),
    keyword_rows INTEGER NOT NULL DEFAULT 0,
    processed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_from_run_id BIGINT REFERENCES radar_processing_runs(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_radar_news_keyword_processing_month
    ON radar_news_keyword_processing (month_start);

CREATE INDEX IF NOT EXISTS idx_radar_news_keyword_processing_status
    ON radar_news_keyword_processing (status);

DROP TRIGGER IF EXISTS trg_radar_news_keyword_processing_updated_at ON radar_news_keyword_processing;
CREATE TRIGGER trg_radar_news_keyword_processing_updated_at
BEFORE UPDATE ON radar_news_keyword_processing
FOR EACH ROW
EXECUTE FUNCTION set_radar_keywords_updated_at();
