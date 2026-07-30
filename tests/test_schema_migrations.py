"""Regression tests for database schema migrations."""

from datetime import date

from tests.conftest import DB_DIR


def _affected_periods_status_constraint(cur):
    cur.execute(
        """
        SELECT pg_get_constraintdef(oid)
          FROM pg_constraint
         WHERE conrelid = 'radar_affected_periods'::regclass
           AND conname = 'radar_affected_periods_status_check'
        """
    )
    return cur.fetchone()[0]


def test_migration_006_upgrades_old_affected_periods_constraint(
    clean_tables, db_conn
):
    """Migration 006 allows an old database to persist the consumed status."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            ALTER TABLE radar_affected_periods
            DROP CONSTRAINT radar_affected_periods_status_check
            """
        )
        cur.execute(
            """
            ALTER TABLE radar_affected_periods
            ADD CONSTRAINT radar_affected_periods_status_check
            CHECK (status IN (
                'pending', 'processing', 'completed', 'failed', 'skipped'
            ))
            """
        )
        cur.execute(
            """
            INSERT INTO radar_affected_periods (
                year, month, month_start, status
            ) VALUES (2024, 3, %s, 'completed')
            RETURNING id
            """,
            (date(2024, 3, 1),),
        )
        period_id = cur.fetchone()[0]

        assert "consumed" not in _affected_periods_status_constraint(cur)

        migration_sql = (
            DB_DIR / "006_alter_affected_periods_add_consumed.sql"
        ).read_text(encoding="utf-8")
        cur.execute(migration_sql)

        assert "consumed" in _affected_periods_status_constraint(cur)
        cur.execute(
            "UPDATE radar_affected_periods SET status = 'consumed' WHERE id = %s",
            (period_id,),
        )
        cur.execute(
            "SELECT status FROM radar_affected_periods WHERE id = %s",
            (period_id,),
        )
        assert cur.fetchone()[0] == "consumed"
