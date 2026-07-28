"""Integration tests for the Radar TRH pipeline against radar_test.

These tests seed the test database with minimal raw news, run the real pipeline
stages with injected dependencies, and assert that periods and aggregates move
through the expected statuses.
"""

from __future__ import annotations

from datetime import date, datetime

import scripts.build_monthly_aggregates as bma
import scripts.detect_affected_periods as dap
import scripts.extract_keywords as ek
from tests.conftest import fresh_connection


NEWS_FIXTURES = [
    {
        "noticia_hash": "int_hash_001",
        "fuente": "Fuente A",
        "url_original": "https://example.com/1",
        "titulo": "Paro docente en Santiago del Estero",
        "texto_completo": (
            "El paro docente afecta a la provincia de Santiago del Estero. "
            "La medida de fuerza docente continúa durante la semana."
        ),
        "fecha_publicacion": datetime(2024, 3, 15, 10, 0, 0),
    },
    {
        "noticia_hash": "int_hash_002",
        "fuente": "Fuente B",
        "url_original": "https://example.com/2",
        "titulo": "La Banda: conflicto docente",
        "texto_completo": (
            "En la ciudad de La Banda continúa el conflicto docente. "
            "Los docentes reclaman mejoras salariales."
        ),
        "fecha_publicacion": datetime(2024, 3, 20, 12, 0, 0),
    },
]


def _seed_raw_news(conn):
    """Insert the integration fixture news into radar_raw_noticias."""
    with conn.cursor() as cur:
        for item in NEWS_FIXTURES:
            cur.execute(
                """
                INSERT INTO radar_raw_noticias (
                    noticia_hash, fuente, url_original, titulo,
                    texto_completo, fecha_publicacion, fecha_extraccion
                ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    item["noticia_hash"],
                    item["fuente"],
                    item["url_original"],
                    item["titulo"],
                    item["texto_completo"],
                    item["fecha_publicacion"],
                ),
            )


def _count_rows(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]


def _get_period_status(conn, month_start: date):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT status FROM radar_affected_periods WHERE month_start = %s",
            (month_start,),
        )
        row = cur.fetchone()
        return row[0] if row else None


def test_detect_affected_periods_creates_expected_period(clean_tables, db_conn):
    """A full detect run inserts a pending period for the seeded month."""
    _seed_raw_news(db_conn)
    db_conn.commit()

    with fresh_connection() as conn:
        inserted = dap.main(argv=["--full"], conn=conn)

    assert inserted == 1
    assert _get_period_status(db_conn, date(2024, 3, 1)) == "pending"


def test_extract_keywords_processes_pending_periods(
    clean_tables, db_conn, fake_nlp, fake_yake
):
    """Keyword extraction completes pending periods and writes keyword rows."""
    _seed_raw_news(db_conn)
    db_conn.commit()

    with fresh_connection() as conn:
        dap.main(argv=["--full"], conn=conn)

    with fresh_connection() as conn:
        ek.main(argv=[], conn=conn, nlp=fake_nlp, yake_extractor=fake_yake)

    assert _get_period_status(db_conn, date(2024, 3, 1)) == "completed"
    assert _count_rows(db_conn, "radar_news_keywords") > 0
    assert _count_rows(db_conn, "radar_monthly_keyword_stats") > 0

    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
              FROM radar_news_keywords
             WHERE canonical_keyword = 'Santiago del Estero'
            """
        )
        assert cur.fetchone()[0] > 0


def test_build_monthly_aggregates_builds_and_consumes(
    clean_tables, db_conn, fake_nlp, fake_yake
):
    """Build aggregates for completed periods and mark them consumed."""
    _seed_raw_news(db_conn)
    db_conn.commit()

    with fresh_connection() as conn:
        dap.main(argv=["--full"], conn=conn)

    with fresh_connection() as conn:
        ek.main(argv=[], conn=conn, nlp=fake_nlp, yake_extractor=fake_yake)

    with fresh_connection() as conn:
        processed = bma.main(argv=[], conn=conn)

    assert processed == 1
    assert _get_period_status(db_conn, date(2024, 3, 1)) == "consumed"
    assert _count_rows(db_conn, "radar_monthly_overview") == 1
    assert _count_rows(db_conn, "radar_daily_activity") == 2
    assert _count_rows(db_conn, "radar_source_monthly_stats") == 2
    assert _count_rows(db_conn, "radar_source_keyword_stats") > 0


def test_build_monthly_aggregates_idempotent_for_consumed_period(
    clean_tables, db_conn, fake_nlp, fake_yake
):
    """Re-running the build for a consumed month does not rebuild aggregates."""
    _seed_raw_news(db_conn)
    db_conn.commit()

    with fresh_connection() as conn:
        dap.main(argv=["--full"], conn=conn)

    with fresh_connection() as conn:
        ek.main(argv=[], conn=conn, nlp=fake_nlp, yake_extractor=fake_yake)

    with fresh_connection() as conn:
        bma.main(argv=[], conn=conn)

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT updated_at FROM radar_monthly_overview WHERE month_start = %s",
            (date(2024, 3, 1),),
        )
        first_updated_at = cur.fetchone()[0]

    with fresh_connection() as conn:
        processed = bma.main(argv=[], conn=conn)

    assert processed == 0
    assert _get_period_status(db_conn, date(2024, 3, 1)) == "consumed"

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT updated_at FROM radar_monthly_overview WHERE month_start = %s",
            (date(2024, 3, 1),),
        )
        second_updated_at = cur.fetchone()[0]

    assert second_updated_at == first_updated_at
