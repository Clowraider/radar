"""Unit tests for scripts/build_monthly_aggregates.py.

These tests mock the PostgreSQL connection/cursor so they do not require a
running database.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

import scripts.build_monthly_aggregates as bma


@pytest.fixture
def mock_conn():
    """Return a mocked psycopg2 connection with a cursor ready for assertions."""
    conn = MagicMock()
    cur = MagicMock()
    cur.rowcount = 0
    cur.fetchone.return_value = [1]
    cur.fetchall.return_value = [(date(2024, 3, 1),)]
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cur
    return conn


def _args(**kwargs):
    """Build a minimal argparse-like namespace for select_months."""
    defaults = {
        "full": False,
        "period": None,
        "include_processing": False,
    }
    defaults.update(kwargs)
    return MagicMock(**defaults)


def _find_execute_call(cur, needle):
    """Return the first execute call whose SQL contains *needle*."""
    for call in cur.execute.call_args_list:
        sql = call.args[0] if call.args else call.kwargs.get("sql", "")
        if needle in sql:
            return call
    return None


def test_select_months_default_uses_completed(mock_conn):
    args = _args(full=False, include_processing=False)
    bma.select_months(mock_conn, args)

    call = _find_execute_call(mock_conn.cursor.return_value, "radar_affected_periods")
    assert call is not None
    sql, params = call.args
    assert "status = ANY(%s)" in sql
    assert params == (["completed"],)


def test_select_months_include_processing_includes_processing_status(mock_conn):
    args = _args(full=False, include_processing=True)
    bma.select_months(mock_conn, args)

    call = _find_execute_call(mock_conn.cursor.return_value, "radar_affected_periods")
    sql, params = call.args
    assert params == (["completed", "processing"],)


def test_select_months_full_queries_raw_noticias(mock_conn):
    args = _args(full=True)
    bma.select_months(mock_conn, args)

    sql = mock_conn.cursor.return_value.execute.call_args.args[0]
    assert "FROM radar_raw_noticias" in sql
    assert "radar_affected_periods" not in sql


def test_select_months_period_returns_single_month(mock_conn):
    args = _args(period=date(2024, 5, 1))
    months = bma.select_months(mock_conn, args)

    assert months == [date(2024, 5, 1)]
    mock_conn.cursor.return_value.execute.assert_not_called()


def test_mark_month_consumed_updates_status(mock_conn):
    bma.mark_month_consumed(mock_conn, date(2024, 3, 1))

    call = mock_conn.cursor.return_value.execute.call_args
    sql, params = call.args
    assert "UPDATE radar_affected_periods" in sql
    assert "SET status = %s" in sql
    assert params == ("consumed", date(2024, 3, 1))


@patch("scripts.build_monthly_aggregates.acquire_script_lock")
@patch("scripts.build_monthly_aggregates.load_env_file")
@patch("scripts.build_monthly_aggregates.db_config", return_value={})
@patch("scripts.build_monthly_aggregates.psycopg2.connect")
def test_main_default_marks_completed_as_consumed(connect_mock, _db_config_mock, _load_env_mock, _lock_mock, mock_conn):
    connect_mock.return_value = mock_conn

    result = bma.main([])

    assert result == 1
    cur = mock_conn.cursor.return_value
    select_call = _find_execute_call(cur, "radar_affected_periods")
    assert select_call.args[1] == (["completed"],)
    consume_call = _find_execute_call(cur, "UPDATE radar_affected_periods")
    assert consume_call is not None
    assert consume_call.args[1] == ("consumed", date(2024, 3, 1))


@patch("scripts.build_monthly_aggregates.acquire_script_lock")
@patch("scripts.build_monthly_aggregates.load_env_file")
@patch("scripts.build_monthly_aggregates.db_config", return_value={})
@patch("scripts.build_monthly_aggregates.psycopg2.connect")
def test_main_full_does_not_mark_consumed(connect_mock, _db_config_mock, _load_env_mock, _lock_mock, mock_conn):
    connect_mock.return_value = mock_conn

    result = bma.main(["--full"])

    assert result == 1
    cur = mock_conn.cursor.return_value
    select_call = _find_execute_call(cur, "radar_raw_noticias")
    assert select_call is not None
    consume_call = _find_execute_call(cur, "UPDATE radar_affected_periods")
    assert consume_call is None


@patch("scripts.build_monthly_aggregates.acquire_script_lock")
@patch("scripts.build_monthly_aggregates.load_env_file")
@patch("scripts.build_monthly_aggregates.db_config", return_value={})
@patch("scripts.build_monthly_aggregates.psycopg2.connect")
def test_main_period_marks_consumed(connect_mock, _db_config_mock, _load_env_mock, _lock_mock, mock_conn):
    connect_mock.return_value = mock_conn

    result = bma.main(["--period", "2024-03"])

    assert result == 1
    cur = mock_conn.cursor.return_value
    consume_call = _find_execute_call(cur, "UPDATE radar_affected_periods")
    assert consume_call is not None
    assert consume_call.args[1] == ("consumed", date(2024, 3, 1))


@patch("scripts.build_monthly_aggregates.acquire_script_lock")
@patch("scripts.build_monthly_aggregates.load_env_file")
@patch("scripts.build_monthly_aggregates.db_config", return_value={})
@patch("scripts.build_monthly_aggregates.psycopg2.connect")
def test_main_no_periods_exits_without_consuming(connect_mock, _db_config_mock, _load_env_mock, _lock_mock, mock_conn):
    mock_conn.cursor.return_value.fetchall.return_value = []
    connect_mock.return_value = mock_conn

    result = bma.main([])

    assert result == 0
    cur = mock_conn.cursor.return_value
    consume_call = _find_execute_call(cur, "UPDATE radar_affected_periods")
    assert consume_call is None
