#!/usr/bin/env python3
"""
sync_trh_raw_to_radar.py

Copy raw news from the existing TRH database into the new Radar TRH database.

This script intentionally copies only source/raw information:
- no TRH keywords
- no TRH clusters
- no TRH scores
- no TRH editorial processing state

First full sync:
    python scripts/sync_trh_raw_to_radar.py --full

Periodic cron sync:
    python scripts/sync_trh_raw_to_radar.py

Incremental sync copies only rows extracted in the last 48 hours that already
have embeddings.
"""

import argparse
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"

sys.path.insert(0, str(PROJECT_ROOT))

from radar_common import AlreadyRunning, acquire_script_lock, db_config, env_int, load_env_file


def build_source_query(full=False):
    base = """
        SELECT
            id AS trh_noticia_id,
            noticia_hash,
            fuente,
            url_original,
            titulo,
            texto_completo,
            url_imagen,
            fecha_publicacion,
            fecha_extraccion,
            embedding::text AS embedding
        FROM noticias_historico
        WHERE noticia_hash IS NOT NULL
          AND url_original IS NOT NULL
          AND titulo IS NOT NULL
    """
    if not full:
        base += """
          AND fecha_extraccion >= NOW() - (%s || ' hours')::interval
          AND embedding IS NOT NULL
        """
    base += """
        ORDER BY fecha_extraccion, id
        LIMIT %s OFFSET %s
    """
    return base


def fetch_batch(src_conn, *, full, lookback_hours, limit, offset):
    query = build_source_query(full=full)
    params = (limit, offset) if full else (lookback_hours, limit, offset)
    with src_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        return cur.fetchall()


def upsert_batch(dst_conn, rows):
    if not rows:
        return 0

    values = []
    for row in rows:
        embedding = row.get("embedding")
        values.append((
            row.get("trh_noticia_id"),
            row.get("noticia_hash"),
            row.get("fuente"),
            row.get("url_original"),
            row.get("titulo"),
            row.get("texto_completo"),
            row.get("url_imagen"),
            row.get("fecha_publicacion"),
            row.get("fecha_extraccion"),
            embedding,
            embedding,
        ))

    sql = """
        INSERT INTO radar_raw_noticias (
            trh_noticia_id,
            noticia_hash,
            fuente,
            url_original,
            titulo,
            texto_completo,
            url_imagen,
            fecha_publicacion,
            fecha_extraccion,
            embedding,
            synced_at
        ) VALUES %s
        ON CONFLICT (noticia_hash) DO UPDATE SET
            trh_noticia_id = EXCLUDED.trh_noticia_id,
            fuente = EXCLUDED.fuente,
            url_original = EXCLUDED.url_original,
            titulo = EXCLUDED.titulo,
            texto_completo = EXCLUDED.texto_completo,
            url_imagen = EXCLUDED.url_imagen,
            fecha_publicacion = EXCLUDED.fecha_publicacion,
            fecha_extraccion = EXCLUDED.fecha_extraccion,
            embedding = EXCLUDED.embedding,
            synced_at = NOW()
    """

    template = """
        (%s, %s, %s, %s, %s, %s, %s, %s, %s,
         CASE WHEN %s IS NULL THEN NULL ELSE %s::vector END,
         NOW())
    """

    with dst_conn.cursor() as cur:
        execute_values(cur, sql, values, template=template, page_size=len(values))
    return len(values)


def sync(full=False, lookback_hours=48, batch_size=1000):
    dst_conn = psycopg2.connect(**db_config("RADAR"))
    src_conn = None

    total = 0
    offset = 0

    try:
        acquire_script_lock(dst_conn, "sync_trh_raw_to_radar")
        src_conn = psycopg2.connect(**db_config("TRH"))
        while True:
            rows = fetch_batch(
                src_conn,
                full=full,
                lookback_hours=lookback_hours,
                limit=batch_size,
                offset=offset,
            )
            if not rows:
                break

            copied = upsert_batch(dst_conn, rows)
            dst_conn.commit()

            total += copied
            offset += batch_size
            print(f"sync batch: {copied} rows | total: {total}")

            if copied < batch_size:
                break

        print(f"sync complete | mode={'full' if full else 'incremental'} | rows upserted: {total}")
        return total
    except Exception:
        dst_conn.rollback()
        raise
    finally:
        if src_conn is not None:
            src_conn.close()
        dst_conn.close()


def main(argv=None):
    load_env_file()

    parser = argparse.ArgumentParser(description="Sync raw TRH news into Radar DB")
    parser.add_argument("--full", action="store_true", help="copy all source rows")
    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=env_int("RADAR_SYNC_LOOKBACK_HOURS", 48),
        help="incremental lookback window in hours for cron runs",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=env_int("RADAR_SYNC_BATCH_SIZE", 1000),
        help="rows per batch",
    )
    args = parser.parse_args(argv)

    if args.batch_size <= 0:
        raise RuntimeError("--batch-size debe ser mayor a 0")
    if not args.full and args.lookback_hours <= 0:
        raise RuntimeError("--lookback-hours debe ser mayor a 0")

    sync(full=args.full, lookback_hours=args.lookback_hours, batch_size=args.batch_size)


if __name__ == "__main__":
    try:
        main()
    except AlreadyRunning as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(0)
    except Exception as exc:
        print(f"sync error: {exc}", file=sys.stderr)
        sys.exit(1)
