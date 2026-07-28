#!/usr/bin/env python3
"""
Detect Radar monthly periods affected by newly synced news.

Default incremental mode uses Radar ingestion time (`synced_at`) because the sync
copies recently indexed TRH rows into Radar. Use `--from-extraction-date` to use
TRH's `fecha_extraccion` instead. Analytics periods are always grouped by
`fecha_publicacion`.

Examples:
    python scripts/detect_affected_periods.py
    python scripts/detect_affected_periods.py --lookback-hours 48
    python scripts/detect_affected_periods.py --from-extraction-date
    python scripts/detect_affected_periods.py --full
"""

import argparse
import os
import sys
import zlib
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"


class AlreadyRunning(RuntimeError):
    pass


def acquire_script_lock(conn, name):
    key = zlib.crc32(f"radar_trh:{name}".encode("utf-8")) & 0x7FFFFFFF
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", (key,))
        acquired = cur.fetchone()[0]
    if not acquired:
        raise AlreadyRunning(f"{name}: ya hay otra ejecución activa; saliendo sin hacer cambios")


def load_env_file(path=ENV_PATH):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def db_config(prefix="RADAR"):
    password = os.getenv(f"{prefix}_DB_PASSWORD")
    if not password:
        raise RuntimeError(f"Falta {prefix}_DB_PASSWORD en .env")
    return {
        "host": os.getenv(f"{prefix}_DB_HOST", "127.0.0.1"),
        "port": env_int(f"{prefix}_DB_PORT", 5432),
        "dbname": os.getenv(f"{prefix}_DB_NAME"),
        "user": os.getenv(f"{prefix}_DB_USER", "postgres"),
        "password": password,
    }


def create_run(conn, *, full, lookback_hours, notes):
    run_type = "full" if full else "incremental"
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO radar_processing_runs (run_type, status, lookback_hours, notes)
            VALUES (%s, 'running', %s, %s)
            RETURNING id
            """,
            (run_type, None if full else lookback_hours, notes),
        )
        return cur.fetchone()[0]


def finish_run(conn, run_id, *, status, rows_detected, notes=None):
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


def detect_periods(conn, *, full, lookback_hours, from_extraction_date):
    if full:
        where_clause = "fecha_publicacion IS NOT NULL"
        params = ()
    elif from_extraction_date:
        where_clause = """
            fecha_publicacion IS NOT NULL
            AND fecha_extraccion >= NOW() - (%s || ' hours')::interval
        """
        params = (lookback_hours,)
    else:
        where_clause = """
            fecha_publicacion IS NOT NULL
            AND synced_at >= NOW() - (%s || ' hours')::interval
        """
        params = (lookback_hours,)

    query = f"""
        SELECT
            DATE_TRUNC('month', fecha_publicacion)::date AS month_start,
            EXTRACT(YEAR FROM fecha_publicacion)::int AS year,
            EXTRACT(MONTH FROM fecha_publicacion)::int AS month,
            COUNT(*)::int AS rows_detected
        FROM radar_raw_noticias
        WHERE {where_clause}
        GROUP BY 1, 2, 3
        ORDER BY 1
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        return cur.fetchall()


def upsert_periods(conn, run_id, periods, *, reason):
    if not periods:
        return 0

    values = [
        (
            run_id,
            period["year"],
            period["month"],
            period["month_start"],
            reason,
            period["rows_detected"],
        )
        for period in periods
    ]
    sql = """
        INSERT INTO radar_affected_periods (
            processing_run_id, year, month, month_start, reason, rows_detected
        ) VALUES %s
        ON CONFLICT (month_start, reason) DO UPDATE SET
            processing_run_id = EXCLUDED.processing_run_id,
            year = EXCLUDED.year,
            month = EXCLUDED.month,
            rows_detected = EXCLUDED.rows_detected,
            status = 'pending',
            updated_at = NOW()
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, values, page_size=len(values))
    return len(values)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Detect Radar monthly periods affected by raw news sync")
    parser.add_argument("--full", action="store_true", help="detect all months with published news")
    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=env_int("RADAR_PROCESS_LOOKBACK_HOURS", env_int("RADAR_SYNC_LOOKBACK_HOURS", 48)),
        help="incremental lookback window in hours",
    )
    parser.add_argument(
        "--from-extraction-date",
        action="store_true",
        help="use fecha_extraccion instead of Radar synced_at for incremental detection",
    )
    parser.add_argument("--notes", help="optional note stored on the processing run")
    return parser.parse_args(argv)


def main(argv=None):
    load_env_file()
    args = parse_args(argv)
    if not args.full and args.lookback_hours <= 0:
        raise RuntimeError("--lookback-hours debe ser mayor a 0")

    conn = psycopg2.connect(**db_config("RADAR"))
    run_id = None
    total_rows = 0
    try:
        acquire_script_lock(conn, "detect_affected_periods")
        mode_note = "full" if args.full else ("fecha_extraccion" if args.from_extraction_date else "synced_at")
        run_id = create_run(
            conn,
            full=args.full,
            lookback_hours=args.lookback_hours,
            notes=args.notes or f"detect affected periods by {mode_note}",
        )
        periods = detect_periods(
            conn,
            full=args.full,
            lookback_hours=args.lookback_hours,
            from_extraction_date=args.from_extraction_date,
        )
        total_rows = sum(period["rows_detected"] for period in periods)
        reason = "full_refresh" if args.full else ("recent_extraction" if args.from_extraction_date else "recent_sync")
        inserted = upsert_periods(conn, run_id, periods, reason=reason)
        finish_run(conn, run_id, status="completed", rows_detected=total_rows)
        conn.commit()

        print(f"processing run: {run_id}")
        print(f"mode: {'full' if args.full else 'incremental'} | reason: {reason}")
        print(f"affected periods: {inserted} | rows detected: {total_rows}")
        for period in periods:
            print(f"- {period['month_start']}: {period['rows_detected']} rows")
        return inserted
    except Exception as exc:
        conn.rollback()
        if run_id is not None:
            try:
                finish_run(conn, run_id, status="failed", rows_detected=total_rows, notes=str(exc))
                conn.commit()
            except Exception:
                conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except AlreadyRunning as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(0)
    except Exception as exc:
        print(f"detect affected periods error: {exc}", file=sys.stderr)
        sys.exit(1)
