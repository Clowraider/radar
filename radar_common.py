#!/usr/bin/env python3
"""
Shared helpers for Radar TRH processing scripts.

This module centralizes duplicated utilities from proceso.py and scripts/*.py
so the pipeline stays consistent and easier to maintain.
"""

from __future__ import annotations

import argparse
import os
import zlib
from datetime import date
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"


class AlreadyRunning(RuntimeError):
    """Raised when another instance of the same script is already active."""

    pass


def load_env_file(path: Path = ENV_PATH) -> None:
    """Load KEY=VALUE pairs from a .env file without overwriting existing vars."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env_int(name: str, default: int) -> int:
    """Read an integer environment variable, falling back to default on error."""
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def db_config(prefix: str) -> dict[str, Any]:
    """Build a psycopg2-compatible connection dict from prefixed env vars."""
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
    """Stable PostgreSQL advisory lock key derived from a script name."""
    return zlib.crc32(f"radar_trh:{name}".encode("utf-8")) & 0x7FFFFFFF


def acquire_script_lock(conn, name: str) -> int:
    """Acquire a PostgreSQL advisory lock for the given script name.

    Returns the lock key so callers can release it later if needed.
    Raises AlreadyRunning if the lock is held by another session.
    """
    key = advisory_lock_key(name)
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", (key,))
        acquired = cur.fetchone()[0]

    if not acquired:
        raise AlreadyRunning(f"{name}: ya hay otra ejecución activa; saliendo sin hacer cambios")

    return key


def month_start_from_string(value: str) -> date:
    """Convert a YYYY-MM string into the first day of that month."""
    if not value or not value.strip():
        raise argparse.ArgumentTypeError("period must use YYYY-MM format")

    value = value.strip()
    if not (len(value) == 7 and value[4] == "-"):
        raise argparse.ArgumentTypeError("period must use YYYY-MM format")

    try:
        year, month = int(value[:4]), int(value[5:7])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("period must use YYYY-MM format") from exc

    if not 1 <= month <= 12:
        raise argparse.ArgumentTypeError("month must be between 01 and 12")

    return date(year, month, 1)


def month_bounds(month_start: date) -> tuple[date, date]:
    """Return the inclusive start and exclusive end dates for a month."""
    next_month = date(
        month_start.year + (month_start.month // 12),
        (month_start.month % 12) + 1,
        1,
    )
    return month_start, next_month
