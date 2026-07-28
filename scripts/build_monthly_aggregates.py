#!/usr/bin/env python3
"""
Build Radar TRH monthly MVP aggregates for future UI/API.

These DB aggregates intentionally keep real source/media names. Source aliases
such as "Fuente 1" are a UI/API presentation concern and should be applied only
when rendering user-facing output.

Modes:
    --full              build every month with published news; leave period statuses unchanged
    --period YYYY-MM    build one month and mark it consumed
    default             build affected periods marked completed and mark them consumed
"""

import argparse
import sys
from pathlib import Path

import psycopg2


STATUS_COMPLETED = "completed"
STATUS_CONSUMED = "consumed"


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"

sys.path.insert(0, str(PROJECT_ROOT))

from radar_common import (
    AlreadyRunning,
    acquire_script_lock,
    db_config,
    env_int,
    load_env_file,
    month_bounds,
    month_start_from_string,
)



def create_run(conn, *, full, notes):
    run_type = "full" if full else "incremental"
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO radar_processing_runs (run_type, status, notes)
            VALUES (%s, 'running', %s)
            RETURNING id
            """,
            (run_type, notes),
        )
        return cur.fetchone()[0]


def finish_run(conn, run_id, *, status, rows_detected=0, notes=None):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE radar_processing_runs
               SET status = %s,
                   finished_at = NOW(),
                   rows_detected = %s,
                   notes = COALESCE(%s, notes)
             WHERE id = %s
            """,
            (status, rows_detected, notes, run_id),
        )


def select_months(conn, args):
    if args.period:
        return [args.period]
    with conn.cursor() as cur:
        if args.full:
            cur.execute(
                """
                SELECT DISTINCT DATE_TRUNC('month', fecha_publicacion)::date AS month_start
                FROM radar_raw_noticias
                WHERE fecha_publicacion IS NOT NULL
                ORDER BY 1
                """
            )
            return [row[0] for row in cur.fetchall()]

        statuses = [STATUS_COMPLETED]
        if args.include_processing:
            statuses.append("processing")
        cur.execute(
            """
            SELECT DISTINCT month_start
            FROM radar_affected_periods
            WHERE status = ANY(%s)
            ORDER BY month_start
            """,
            (statuses,),
        )
        return [row[0] for row in cur.fetchall()]


def reset_month(conn, month_start):
    with conn.cursor() as cur:
        for table in [
            "radar_source_keyword_stats",
            "radar_source_monthly_stats",
            "radar_daily_activity",
            "radar_monthly_overview",
        ]:
            cur.execute(f"DELETE FROM {table} WHERE month_start = %s", (month_start,))


def mark_month_consumed(conn, month_start):
    """Mark processed periods as consumed after their aggregate tables have been built."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE radar_affected_periods
               SET status = %s,
                   updated_at = NOW()
             WHERE month_start = %s
               AND status IN ('completed', 'processing')
            """,
            (STATUS_CONSUMED, month_start),
        )


def insert_daily_activity(conn, month_start, run_id):
    start, end = month_bounds(month_start)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO radar_daily_activity (month_start, activity_date, news_count, updated_from_run_id)
            SELECT
                %s,
                fecha_publicacion::date AS activity_date,
                COUNT(*)::int AS news_count,
                %s
            FROM radar_raw_noticias
            WHERE fecha_publicacion >= %s AND fecha_publicacion < %s
            GROUP BY fecha_publicacion::date
            """,
            (month_start, run_id, start, end),
        )
        return cur.rowcount


def insert_source_keyword_stats(conn, month_start, run_id):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO radar_source_keyword_stats (
                month_start, source_media, keyword, normalized_keyword,
                canonical_keyword, normalized_canonical_keyword, keyword_type,
                news_count, total_occurrences, avg_score, updated_from_run_id
            )
            SELECT
                nk.month_start,
                nk.source_media,
                COALESCE(MAX(nk.canonical_keyword), MIN(nk.keyword)) AS keyword,
                nk.normalized_keyword,
                MAX(nk.canonical_keyword) AS canonical_keyword,
                MAX(nk.normalized_canonical_keyword) AS normalized_canonical_keyword,
                MAX(nk.keyword_type) AS keyword_type,
                COUNT(DISTINCT nk.raw_noticia_id)::int AS news_count,
                SUM(nk.occurrences)::int AS total_occurrences,
                AVG(nk.score) AS avg_score,
                %s
            FROM radar_news_keywords nk
            WHERE nk.month_start = %s
            GROUP BY nk.month_start, nk.source_media, nk.normalized_keyword
            """,
            (run_id, month_start),
        )
        return cur.rowcount


def insert_source_monthly_stats(conn, month_start, run_id):
    start, end = month_bounds(month_start)
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH source_news AS (
                SELECT
                    %s::date AS month_start,
                    r.fuente AS source_media,
                    COUNT(r.id)::int AS news_count
                FROM radar_raw_noticias r
                WHERE r.fecha_publicacion >= %s AND r.fecha_publicacion < %s
                GROUP BY r.fuente
            ), keyword_counts AS (
                SELECT
                    month_start,
                    source_media,
                    keyword,
                    normalized_keyword,
                    news_count,
                    total_occurrences,
                    ROW_NUMBER() OVER (
                        PARTITION BY source_media
                        ORDER BY news_count DESC, total_occurrences DESC, keyword
                    ) AS rn
                FROM radar_source_keyword_stats
                WHERE month_start = %s
            ), keyword_summary AS (
                SELECT
                    source_media,
                    SUM(news_count)::int AS keyword_rows,
                    COUNT(DISTINCT normalized_keyword)::int AS distinct_keywords
                FROM keyword_counts
                GROUP BY source_media
            ), top_keywords AS (
                SELECT
                    source_media,
                    jsonb_agg(
                        jsonb_build_object(
                            'keyword', keyword,
                            'news_count', news_count,
                            'total_occurrences', total_occurrences
                        ) ORDER BY rn
                    ) AS top_keywords
                FROM keyword_counts
                WHERE rn <= 10
                GROUP BY source_media
            )
            INSERT INTO radar_source_monthly_stats (
                month_start, source_media, news_count, keyword_rows,
                distinct_keywords, top_keywords, updated_from_run_id
            )
            SELECT
                sn.month_start,
                sn.source_media,
                sn.news_count,
                COALESCE(ks.keyword_rows, 0),
                COALESCE(ks.distinct_keywords, 0),
                COALESCE(tk.top_keywords, '[]'::jsonb),
                %s
            FROM source_news sn
            LEFT JOIN keyword_summary ks ON ks.source_media = sn.source_media
            LEFT JOIN top_keywords tk ON tk.source_media = sn.source_media
            """,
            (month_start, start, end, month_start, run_id),
        )
        return cur.rowcount


def insert_monthly_overview(conn, month_start, run_id):
    start, end = month_bounds(month_start)
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH raw_stats AS (
                SELECT
                    COUNT(*)::int AS total_news,
                    COUNT(DISTINCT r.fuente)::int AS active_source_count,
                    MIN(r.fecha_publicacion) AS first_publication_at,
                    MAX(r.fecha_publicacion) AS last_publication_at
                FROM radar_raw_noticias r
                WHERE r.fecha_publicacion >= %s AND r.fecha_publicacion < %s
            ), keyword_stats AS (
                SELECT
                    COUNT(DISTINCT raw_noticia_id)::int AS news_with_keywords,
                    COUNT(DISTINCT normalized_keyword)::int AS keyword_count
                FROM radar_news_keywords
                WHERE month_start = %s
            ), top_keywords AS (
                SELECT COALESCE(jsonb_agg(item ORDER BY rank_order), '[]'::jsonb) AS top_keywords
                FROM (
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY priority DESC, news_count DESC, total_occurrences DESC, keyword) AS rank_order,
                        jsonb_build_object(
                            'keyword', COALESCE(canonical_keyword, keyword),
                            'type', keyword_type,
                            'news_count', news_count,
                            'total_occurrences', total_occurrences
                        ) AS item
                    FROM radar_monthly_keyword_stats
                    WHERE month_start = %s
                    ORDER BY priority DESC, news_count DESC, total_occurrences DESC, keyword
                    LIMIT 20
                ) ranked
            ), source_stats AS (
                SELECT COALESCE(jsonb_agg(item ORDER BY rank_order), '[]'::jsonb) AS source_stats
                FROM (
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY news_count DESC, source_media) AS rank_order,
                        jsonb_build_object(
                            'source_media', source_media,
                            'news_count', news_count,
                            'distinct_keywords', distinct_keywords
                        ) AS item
                    FROM radar_source_monthly_stats
                    WHERE month_start = %s
                    ORDER BY news_count DESC, source_media
                ) ranked
            )
            INSERT INTO radar_monthly_overview (
                month_start, total_news, news_with_keywords, active_source_count,
                keyword_count, top_keywords, source_stats,
                first_publication_at, last_publication_at, updated_from_run_id
            )
            SELECT
                %s,
                COALESCE(rs.total_news, 0),
                COALESCE(ks.news_with_keywords, 0),
                COALESCE(rs.active_source_count, 0),
                COALESCE(ks.keyword_count, 0),
                tk.top_keywords,
                ss.source_stats,
                rs.first_publication_at,
                rs.last_publication_at,
                %s
            FROM raw_stats rs
            CROSS JOIN keyword_stats ks
            CROSS JOIN top_keywords tk
            CROSS JOIN source_stats ss
            """,
            (start, end, month_start, month_start, month_start, month_start, run_id),
        )
        return cur.rowcount


def build_month(conn, month_start, run_id):
    reset_month(conn, month_start)
    daily_rows = insert_daily_activity(conn, month_start, run_id)
    source_keyword_rows = insert_source_keyword_stats(conn, month_start, run_id)
    source_rows = insert_source_monthly_stats(conn, month_start, run_id)
    overview_rows = insert_monthly_overview(conn, month_start, run_id)
    return {
        "daily_rows": daily_rows,
        "source_keyword_rows": source_keyword_rows,
        "source_rows": source_rows,
        "overview_rows": overview_rows,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Build Radar TRH monthly UI/API aggregates")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--full",
        action="store_true",
        help="build every month with published news; leave radar_affected_periods statuses unchanged",
    )
    mode.add_argument(
        "--period",
        type=month_start_from_string,
        help="build one month in YYYY-MM format and mark it consumed",
    )
    parser.add_argument(
        "--include-processing",
        action="store_true",
        help=(
            "default mode also includes affected periods still marked processing; "
            "all selected periods are marked consumed on success"
        ),
    )
    parser.add_argument("--notes", help="optional note stored on the processing run")
    return parser.parse_args(argv)


def main(argv=None, conn=None):
    args = parse_args(argv)
    own_conn = conn is None
    if own_conn:
        load_env_file()
        conn = psycopg2.connect(**db_config("RADAR"))
    run_id = None
    processed = 0
    try:
        acquire_script_lock(conn, "build_monthly_aggregates")
        run_id = create_run(
            conn,
            full=bool(args.full),
            notes=args.notes or "build monthly aggregates",
        )
        months = select_months(conn, args)
        if not months:
            finish_run(conn, run_id, status="completed", rows_detected=0)
            conn.commit()
            print("no periods selected")
            return 0

        print(f"periods selected: {len(months)}")
        for month_start in months:
            result = build_month(conn, month_start, run_id)
            # Full rebuilds everything independently of the period tracking table;
            # leave existing statuses untouched so the normal pipeline can still
            # detect and consume completed periods incrementally.
            if not args.full:
                mark_month_consumed(conn, month_start)
            conn.commit()
            processed += 1
            print(
                f"{month_start}: overview={result['overview_rows']} "
                f"daily={result['daily_rows']} sources={result['source_rows']} "
                f"source_keywords={result['source_keyword_rows']}"
            )

        finish_run(conn, run_id, status="completed", rows_detected=processed)
        conn.commit()
        print(f"monthly aggregates complete | periods={processed}")
        return processed
    except Exception as exc:
        conn.rollback()
        if run_id is not None:
            try:
                finish_run(conn, run_id, status="failed", rows_detected=processed, notes=str(exc))
                conn.commit()
            except Exception:
                conn.rollback()
        raise
    finally:
        if own_conn:
            conn.close()


if __name__ == "__main__":
    try:
        main()
    except AlreadyRunning as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(0)
    except Exception as exc:
        print(f"build monthly aggregates error: {exc}", file=sys.stderr)
        sys.exit(1)
