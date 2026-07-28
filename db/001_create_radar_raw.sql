-- Radar TRH raw database schema
--
-- Usage example:
--   createdb radar_trh
--   psql radar_trh -f db/001_create_radar_raw.sql
--
-- This schema stores only raw source information copied from TRH.
-- All classification, keywords, clustering, scoring, and analytics should be
-- implemented inside Radar as separate future processes.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS radar_raw_noticias (
    id BIGSERIAL PRIMARY KEY,

    -- Traceability to TRH. Not used as Radar business identity.
    trh_noticia_id INTEGER,

    -- Stable raw identity from TRH.
    noticia_hash VARCHAR(64) NOT NULL UNIQUE,

    -- Raw news fields.
    fuente VARCHAR(100) NOT NULL,
    url_original TEXT NOT NULL,
    titulo TEXT NOT NULL,
    texto_completo TEXT,
    url_imagen TEXT,
    fecha_publicacion TIMESTAMP,
    fecha_extraccion TIMESTAMP,
    embedding vector(768),

    -- Sync metadata.
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    synced_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_radar_raw_noticias_hash
    ON radar_raw_noticias (noticia_hash);

CREATE INDEX IF NOT EXISTS idx_radar_raw_noticias_fuente
    ON radar_raw_noticias (fuente);

CREATE INDEX IF NOT EXISTS idx_radar_raw_noticias_fecha_publicacion
    ON radar_raw_noticias (fecha_publicacion);

CREATE INDEX IF NOT EXISTS idx_radar_raw_noticias_fecha_extraccion
    ON radar_raw_noticias (fecha_extraccion);

CREATE INDEX IF NOT EXISTS idx_radar_raw_noticias_synced_at
    ON radar_raw_noticias (synced_at);

-- Vector index for future semantic features. Safe to keep even before Radar uses it.
CREATE INDEX IF NOT EXISTS idx_radar_raw_noticias_embedding
    ON radar_raw_noticias USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;

CREATE OR REPLACE FUNCTION set_radar_raw_noticias_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_radar_raw_noticias_updated_at ON radar_raw_noticias;
CREATE TRIGGER trg_radar_raw_noticias_updated_at
BEFORE UPDATE ON radar_raw_noticias
FOR EACH ROW
EXECUTE FUNCTION set_radar_raw_noticias_updated_at();
