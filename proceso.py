#!/usr/bin/env python3
"""
Cron-friendly Radar TRH processing orchestrator.

Runs the normal incremental processing chain sequentially:
1. scripts/sync_trh_raw_to_radar.py
2. scripts/detect_affected_periods.py
3. scripts/extract_keywords.py
4. scripts/build_monthly_aggregates.py

The whole chain is protected by a PostgreSQL advisory lock, so a second
`proceso.py` invocation exits without doing work while another one is active.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import psycopg2

from radar_common import (
    AlreadyRunning,
    acquire_script_lock,
    advisory_lock_key,
    db_config,
    env_int,
    load_env_file,
)


PROJECT_ROOT = Path(__file__).resolve().parent
LOCK_NAME = "proceso"

PROCESSING_CHAIN = (
    ("sync raw news", "scripts/sync_trh_raw_to_radar.py"),
    ("detect affected periods", "scripts/detect_affected_periods.py"),
    ("extract keywords", "scripts/extract_keywords.py"),
    ("build monthly aggregates", "scripts/build_monthly_aggregates.py"),
)


def release_process_lock(conn, key: int) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_unlock(%s)", (key,))


def log(message: str, *, stream=sys.stdout) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    print(f"[{timestamp}] {message}", file=stream, flush=True)


def run_step(label: str, script_path: str) -> int:
    command = [sys.executable, "-u", script_path]
    log(f"starting: {label} | command={' '.join(command)}")
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)

    if completed.returncode == 0:
        log(f"completed: {label}")
    else:
        log(
            f"failed: {label} | exit_code={completed.returncode}",
            stream=sys.stderr,
        )

    return completed.returncode


def main() -> int:
    load_env_file()

    conn = None
    lock_key = None

    try:
        conn = psycopg2.connect(**db_config("RADAR"))
        lock_key = acquire_script_lock(conn, LOCK_NAME)
        log("proceso.py start")

        for label, script_path in PROCESSING_CHAIN:
            exit_code = run_step(label, script_path)
            if exit_code != 0:
                log("proceso.py stopped after first failed step", stream=sys.stderr)
                return exit_code

        log("proceso.py complete")
        return 0

    except AlreadyRunning as exc:
        print(exc, file=sys.stderr, flush=True)
        return 0
    except Exception as exc:
        print(f"proceso.py error: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        if conn is not None:
            if lock_key is not None:
                try:
                    release_process_lock(conn, lock_key)
                except Exception as exc:  # pragma: no cover - best-effort cleanup
                    print(f"proceso.py lock release error: {exc}", file=sys.stderr, flush=True)
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
