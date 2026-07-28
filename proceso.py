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

import os
import subprocess
import sys
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"
LOCK_NAME = "proceso"

PROCESSING_CHAIN = (
    ("sync raw news", "scripts/sync_trh_raw_to_radar.py"),
    ("detect affected periods", "scripts/detect_affected_periods.py"),
    ("extract keywords", "scripts/extract_keywords.py"),
    ("build monthly aggregates", "scripts/build_monthly_aggregates.py"),
)


class AlreadyRunning(RuntimeError):
    pass


def load_env_file(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def db_config(prefix: str) -> dict[str, Any]:
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


def advisory_lock_key(name: str) -> int:
    return zlib.crc32(f"radar_trh:{name}".encode("utf-8")) & 0x7FFFFFFF


def acquire_process_lock(conn, name: str = LOCK_NAME) -> int:
    key = advisory_lock_key(name)
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", (key,))
        acquired = cur.fetchone()[0]

    if not acquired:
        raise AlreadyRunning(f"{name}: ya hay otra ejecución activa; saliendo sin hacer cambios")

    return key


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
        lock_key = acquire_process_lock(conn)
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
