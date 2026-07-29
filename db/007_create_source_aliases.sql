-- Stable source aliases for Web UI presentation.
--
-- Real source/media names are mapped to anonymous aliases such as "Fuente 1".
-- This table is populated by the monthly aggregate pipeline; the Web UI only
-- reads from it and never displays raw source names.

CREATE TABLE IF NOT EXISTS radar_source_aliases (
    source_name TEXT PRIMARY KEY,
    alias TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_radar_source_aliases_alias
    ON radar_source_aliases (alias);
