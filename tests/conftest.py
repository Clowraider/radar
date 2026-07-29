"""Shared pytest fixtures for Radar TRH integration tests.

The fixtures point every script at the `radar_test` database and apply the
schema once per session. Each test that requests `clean_tables` starts with an
empty set of Radar tables.
"""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

import psycopg2
import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_DIR = PROJECT_ROOT / "db"
ENV_PATH = PROJECT_ROOT / ".env"

# Load .env into the environment so tests read the same credentials as scripts.
# Override via environment variables is still supported.
sys.path.insert(0, str(PROJECT_ROOT))
from radar_common import load_env_file  # noqa: E402

load_env_file()

SCHEMA_FILES = [
    "001_create_radar_raw.sql",
    "002_create_processing_tables.sql",
    "003_create_keywords_tables.sql",
    "004_create_keyword_processing_state.sql",
    "005_create_monthly_aggregates.sql",
    "006_alter_affected_periods_add_consumed.sql",
    "007_create_source_aliases.sql",
]

TEST_DB_CONFIG = {
    "host": os.environ.get("RADAR_DB_HOST", "192.168.0.106"),
    "port": int(os.environ.get("RADAR_DB_PORT", "5432")),
    "dbname": os.environ.get("RADAR_DB_NAME", "radar_test"),
    "user": os.environ.get("RADAR_DB_USER", "postgres"),
    "password": os.environ.get("RADAR_DB_PASSWORD", ""),
}

RADAR_TABLES = [
    "radar_affected_periods",
    "radar_daily_activity",
    "radar_keyword_aliases",
    "radar_keyword_dictionary",
    "radar_monthly_keyword_stats",
    "radar_monthly_overview",
    "radar_news_keyword_processing",
    "radar_news_keywords",
    "radar_processing_runs",
    "radar_raw_noticias",
    "radar_source_aliases",
    "radar_source_keyword_stats",
    "radar_source_monthly_stats",
]


@pytest.fixture(scope="session", autouse=True)
def radar_test_env():
    """Override Radar environment variables to target the test database."""
    overrides = {
        "RADAR_DB_HOST": TEST_DB_CONFIG["host"],
        "RADAR_DB_PORT": str(TEST_DB_CONFIG["port"]),
        "RADAR_DB_NAME": TEST_DB_CONFIG["dbname"],
        "RADAR_DB_USER": TEST_DB_CONFIG["user"],
        "RADAR_DB_PASSWORD": TEST_DB_CONFIG["password"],
    }
    original = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    yield
    for key, value in original.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _apply_schema(conn):
    """Apply the Radar SQL schema files to the connected database."""
    with conn.cursor() as cur:
        for filename in SCHEMA_FILES:
            cur.execute((DB_DIR / filename).read_text(encoding="utf-8"))


def _truncate_all_tables(conn):
    """Remove all rows from Radar tables and reset their sequences."""
    with conn.cursor() as cur:
        cur.execute(
            f"TRUNCATE TABLE {', '.join(RADAR_TABLES)} RESTART IDENTITY CASCADE"
        )


@pytest.fixture(scope="session")
def schema_applied():
    """Apply the schema once per test session."""
    conn = psycopg2.connect(**TEST_DB_CONFIG)
    try:
        _apply_schema(conn)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def db_conn(schema_applied):
    """Yield a connection to the test database."""
    conn = psycopg2.connect(**TEST_DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def clean_tables(schema_applied):
    """Truncate all Radar tables before the test runs."""
    conn = psycopg2.connect(**TEST_DB_CONFIG)
    try:
        _truncate_all_tables(conn)
        conn.commit()
    finally:
        conn.close()


@contextlib.contextmanager
def fresh_connection():
    """Open a fresh connection for a script invocation and close it afterwards.

    Each pipeline script acquires a PostgreSQL advisory lock. Using a dedicated
    connection per invocation prevents leftover locks from interfering with
    subsequent calls in the same test.
    """
    conn = psycopg2.connect(**TEST_DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def fake_nlp():
    """Return a lightweight fake spaCy pipeline for integration tests.

    The real `es_core_news_lg` model is not required in CI environments; this
    fixture returns a deterministic entity for every document so the keyword
    extraction -> aggregate pipeline can be exercised end-to-end.
    """
    class FakeEnt:
        def __init__(self, text, label_):
            self.text = text
            self.label_ = label_

    class FakeDoc:
        def __init__(self, ents):
            self.ents = ents

    class FakeNLP:
        def __init__(self):
            self._ents = [FakeEnt("Test Organization", "ORG")]

        def __call__(self, text):
            return FakeDoc(self._ents)

    return FakeNLP()


@pytest.fixture
def fake_yake():
    """Return a lightweight fake YAKE extractor for integration tests."""
    class FakeYAKE:
        def extract_keywords(self, text):
            # YAKE returns tuples of (phrase, score); lower score is better.
            return [("integration test", 0.5)]

    return FakeYAKE()
