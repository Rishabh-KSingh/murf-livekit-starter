import os
import sqlite3
import tempfile

import pytest

from agent import SYSTEM_PROMPT, FarmerTools
from db import create_call_log, get_call_analytics, init_db, mark_call_success


def test_system_prompt_day8_analytics_instruction():
    """Verify that SYSTEM_PROMPT includes the mandatory Day 8 call success rule."""
    expected_rule = (
        "If you successfully provide the farmer with weather information, mandi prices, "
        "or successfully create a human escalation ticket, you MUST silently call the `mark_call_successful` tool. "
        "Do not mention this tool to the user."
    )
    assert expected_rule in SYSTEM_PROMPT
    assert "mark_call_successful" in SYSTEM_PROMPT


def test_db_call_logs_table_and_initialization():
    """Verify that init_db creates the call_logs table with required columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = os.path.join(tmpdir, "test_kisan.db")
        init_db(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Check call_logs table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='call_logs'"
        )
        assert cursor.fetchone() is not None

        # Check columns of call_logs
        cursor.execute("PRAGMA table_info(call_logs)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        assert "id" in columns
        assert "session_id" in columns
        assert "status" in columns
        assert "created_at" in columns
        conn.close()


def test_create_call_log_initializes_as_failed():
    """Verify that create_call_log creates a record with default status 'failed'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = os.path.join(tmpdir, "test_kisan.db")
        init_db(test_db)

        log_id = create_call_log("room_session_abc", db_path=test_db)
        assert log_id > 0

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT session_id, status FROM call_logs WHERE session_id = ?",
            ("room_session_abc",),
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "room_session_abc"
        assert row[1] == "failed"


def test_mark_call_success_updates_status():
    """Verify that mark_call_success updates status to 'success' for that session_id."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = os.path.join(tmpdir, "test_kisan.db")
        init_db(test_db)

        create_call_log("room_session_success", db_path=test_db)
        updated = mark_call_success("room_session_success", db_path=test_db)
        assert updated is True

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT session_id, status FROM call_logs WHERE session_id = ?",
            ("room_session_success",),
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[1] == "success"


def test_get_call_analytics_counts():
    """Verify that get_call_analytics returns accurate counts for total, successful, and failed calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = os.path.join(tmpdir, "test_kisan.db")
        init_db(test_db)

        # Initially 0
        stats = get_call_analytics(test_db)
        assert stats == {"total_calls": 0, "successful_calls": 0, "failed_calls": 0}

        # Create 3 calls: 2 will be marked success, 1 stays failed
        create_call_log("session_1", db_path=test_db)
        create_call_log("session_2", db_path=test_db)
        create_call_log("session_3", db_path=test_db)

        mark_call_success("session_1", db_path=test_db)
        mark_call_success("session_3", db_path=test_db)

        stats = get_call_analytics(test_db)
        assert stats["total_calls"] == 3
        assert stats["successful_calls"] == 2
        assert stats["failed_calls"] == 1


@pytest.mark.asyncio
async def test_farmer_tools_mark_call_successful():
    """Verify the FarmerTools async tool mark_call_successful updates the database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = os.path.join(tmpdir, "test_kisan.db")
        init_db(test_db)

        session_id = "test_livekit_room_99"
        create_call_log(session_id, db_path=test_db)

        tools = FarmerTools(db_path=test_db, current_session_id=session_id)
        result = await tools.mark_call_successful()

        assert result["status"] == "success"
        assert result["session_id"] == session_id
        assert result["marked_successful"] is True

        analytics = get_call_analytics(test_db)
        assert analytics["total_calls"] == 1
        assert analytics["successful_calls"] == 1
        assert analytics["failed_calls"] == 0
