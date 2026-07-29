"""Integration tests for stable source aliases.

These tests run the aggregate pipeline against the radar_test database and
verify that radar_source_aliases is populated with stable, deterministic
"Fuente N" aliases.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

import scripts.build_monthly_aggregates as bma
import scripts.detect_affected_periods as dap
import scripts.extract_keywords as ek
from tests.conftest import fresh_connection


NEWS_FIXTURES = [
    {
        "noticia_hash": "alias_hash_001",
        "fuente": "Source B",
        "url_original": "https://example.com/1",
        "titulo": "Paro docente en Santiago del Estero",
        "texto_completo": (
            "El paro docente afecta a la provincia de Santiago del Estero. "
            "La medida de fuerza docente continúa durante la semana."
        ),
        "fecha_publicacion": datetime(2024, 3, 15, 10, 0, 0),
    },
    {
        "noticia_hash": "alias_hash_002",
        "fuente": "Source A",
        "url_original": "https://example.com/2",
        "titulo": "La Banda: conflicto docente",
        "texto_completo": (
            "En la ciudad de La Banda continúa el conflicto docente. "
            "Los docentes reclaman mejoras salariales."
        ),
        "fecha_publicacion": datetime(2024, 3, 20, 12, 0, 0),
    },
]


def _seed_raw_news(conn, fixtures):
    """Insert fixture news into radar_raw_noticias."""
    with conn.cursor() as cur:
        for item in fixtures:
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


def _get_alias(conn, source_name: str):
    """Return the alias for a source_name or None."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT alias FROM radar_source_aliases WHERE source_name = %s",
            (source_name,),
        )
        row = cur.fetchone()
        return row[0] if row else None


def _get_aliases(conn):
    """Return all source_name -> alias mappings ordered by source_name."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT source_name, alias FROM radar_source_aliases ORDER BY source_name"
        )
        return cur.fetchall()


@pytest.fixture
def seed_and_process(clean_tables, db_conn, fake_nlp, fake_yake):
    """Seed news and run the full pipeline up to monthly aggregates."""
    _seed_raw_news(db_conn, NEWS_FIXTURES)
    db_conn.commit()

    with fresh_connection() as conn:
        dap.main(argv=["--full"], conn=conn)

    with fresh_connection() as conn:
        ek.main(argv=[], conn=conn, nlp=fake_nlp, yake_extractor=fake_yake)

    with fresh_connection() as conn:
        bma.main(argv=[], conn=conn)

    return db_conn


def test_pipeline_creates_stable_aliases(seed_and_process, db_conn):
    """New sources receive deterministic Fuente N aliases."""
    aliases = _get_aliases(db_conn)
    assert len(aliases) == 2

    # Alphabetically: Source A < Source B, so A gets Fuente 1 and B gets Fuente 2.
    assert aliases == [
        ("Source A", "Fuente 1"),
        ("Source B", "Fuente 2"),
    ]


def test_pipeline_preserves_existing_aliases(seed_and_process, db_conn, fake_nlp, fake_yake):
    """Re-running the pipeline does not change existing aliases."""
    first_alias_a = _get_alias(db_conn, "Source A")
    first_alias_b = _get_alias(db_conn, "Source B")

    # Re-run the aggregate pipeline without any new sources.
    with fresh_connection() as conn:
        bma.main(argv=[], conn=conn)

    assert _get_alias(db_conn, "Source A") == first_alias_a
    assert _get_alias(db_conn, "Source B") == first_alias_b


def test_pipeline_assigns_next_alias_to_new_source(
    seed_and_process, db_conn, fake_nlp, fake_yake
):
    """A new source added after the first run gets the next available number."""
    new_fixture = [
        {
            "noticia_hash": "alias_hash_003",
            "fuente": "Source C",
            "url_original": "https://example.com/3",
            "titulo": "Nuevo conflicto salarial",
            "texto_completo": "El nuevo conflicto salarial afecta a docentes.",
            "fecha_publicacion": datetime(2024, 4, 1, 10, 0, 0),
        }
    ]
    _seed_raw_news(db_conn, new_fixture)
    db_conn.commit()

    with fresh_connection() as conn:
        dap.main(argv=["--full"], conn=conn)

    with fresh_connection() as conn:
        ek.main(argv=[], conn=conn, nlp=fake_nlp, yake_extractor=fake_yake)

    with fresh_connection() as conn:
        bma.main(argv=[], conn=conn)

    assert _get_alias(db_conn, "Source A") == "Fuente 1"
    assert _get_alias(db_conn, "Source B") == "Fuente 2"
    assert _get_alias(db_conn, "Source C") == "Fuente 3"


def test_ensure_source_aliases_empty_months_returns_zero(clean_tables, db_conn):
    """ensure_source_aliases is a no-op when no months are processed."""
    assert bma.ensure_source_aliases(db_conn, []) == 0


def test_ensure_source_aliases_skips_existing_sources(clean_tables, db_conn):
    """ensure_source_aliases only inserts aliases for sources not yet mapped."""
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO radar_source_aliases (source_name, alias) VALUES (%s, %s)",
            ("Source A", "Fuente 1"),
        )
        cur.execute(
            """
            INSERT INTO radar_source_monthly_stats (
                month_start, source_media, news_count, updated_from_run_id
            ) VALUES (%s, %s, %s, NULL)
            """,
            (date(2024, 3, 1), "Source A", 5),
        )
        cur.execute(
            """
            INSERT INTO radar_source_monthly_stats (
                month_start, source_media, news_count, updated_from_run_id
            ) VALUES (%s, %s, %s, NULL)
            """,
            (date(2024, 3, 1), "Source B", 3),
        )
    db_conn.commit()

    inserted = bma.ensure_source_aliases(db_conn, [date(2024, 3, 1)])
    assert inserted == 1
    assert _get_alias(db_conn, "Source B") == "Fuente 2"
    assert _get_alias(db_conn, "Source A") == "Fuente 1"
