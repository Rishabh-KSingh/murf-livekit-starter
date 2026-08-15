import json
import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger("agent.db")

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_DIR, "kisan_mitra.db")


def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Initializes the SQLite database tables (users and call_logs)."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # 1. Users table for caller profiles & memory
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            language_preference TEXT,
            facts TEXT,
            last_interaction TIMESTAMP
        )
        """
    )

    # 2. Call logs table for Day 8 Call Analytics
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS call_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'failed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Seed default user profiles for testing / demo
    rishabh_facts = json.dumps(
        {"district": "Sheikhpura", "crop": "Moong", "name": "Rishabh"},
        ensure_ascii=False,
    )
    cursor.execute(
        """
        INSERT INTO users (user_id, name, language_preference, facts, last_interaction)
        VALUES
            ('user_123', 'ऋषभ', 'Hindi', ?, datetime('now')),
            ('sip_rishabh_kisan1', 'ऋषभ', 'Hindi', ?, datetime('now')),
            ('rishabh_kisan1', 'ऋषभ', 'Hindi', ?, datetime('now'))
        ON CONFLICT(user_id) DO UPDATE SET
            name='ऋषभ',
            facts=excluded.facts,
            last_interaction=excluded.last_interaction
        """,
        (rishabh_facts, rishabh_facts, rishabh_facts),
    )

    conn.commit()
    conn.close()
    logger.info(f"Database initialized successfully at: {db_path}")


def create_call_log(session_id: str, db_path: str = DB_PATH) -> int:
    """Creates a new call log entry initialized with status 'failed'.

    Args:
        session_id: The unique LiveKit room name or session ID.
        db_path: Path to the SQLite database.

    Returns:
        The inserted row ID.
    """
    sid = (session_id or "").strip()
    if not sid:
        sid = f"session_{int(datetime.now().timestamp())}"

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Ensure table exists
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS call_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'failed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO call_logs (session_id, status, created_at)
        VALUES (?, 'failed', ?)
        """,
        (sid, current_time),
    )
    log_id = cursor.lastrowid or 0
    conn.commit()
    conn.close()
    logger.info(
        f"Created call_log id={log_id} for session_id='{sid}' with status='failed'"
    )
    return log_id


def mark_call_success(session_id: str, db_path: str = DB_PATH) -> bool:
    """Updates the status of the call log to 'success' for the given session_id.

    Args:
        session_id: The unique LiveKit room name or session ID.
        db_path: Path to the SQLite database.

    Returns:
        True if at least one row was updated, False otherwise.
    """
    sid = (session_id or "").strip()
    if not sid:
        logger.warning("mark_call_success called with empty session_id")
        return False

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Ensure table exists
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS call_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'failed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        UPDATE call_logs
        SET status = 'success'
        WHERE session_id = ?
        """,
        (sid,),
    )
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()

    if rows_affected > 0:
        logger.info(
            f"Updated call_log status to 'success' for session_id='{sid}' ({rows_affected} rows)"
        )
        return True
    else:
        logger.warning(f"No call_log found to update for session_id='{sid}'")
        return False


def get_call_analytics(db_path: str = DB_PATH) -> dict:
    """Queries call_logs and returns total_calls, successful_calls, and failed_calls."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Ensure table exists
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS call_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'failed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        SELECT
            COUNT(*) as total_calls,
            COALESCE(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END), 0) as successful_calls,
            COALESCE(SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END), 0) as failed_calls
        FROM call_logs
        """
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        total = int(row["total_calls"] or 0)
        successful = int(row["successful_calls"] or 0)
        failed = int(row["failed_calls"] or 0)
    else:
        total = 0
        successful = 0
        failed = 0

    return {
        "total_calls": total,
        "successful_calls": successful,
        "failed_calls": failed,
    }


if __name__ == "__main__":
    init_db()
    print("Database initialized:", get_call_analytics())
