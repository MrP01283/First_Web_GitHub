import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
DB_PATH = BACKEND_DIR / "history.db"
HISTORY_LIMIT = 100


def get_db_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_text TEXT NOT NULL,
                result_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                limit_value INTEGER NOT NULL,
                mode TEXT NOT NULL,
                source_words INTEGER NOT NULL,
                result_words INTEGER NOT NULL,
                status TEXT NOT NULL,
                error_text TEXT NOT NULL
            )
            """
        )


def save_history_entry(
    source_text: str,
    result_text: str,
    limit_value: int,
    mode: str,
    source_words: int,
    result_words: int,
    status: str,
    error_text: str = "",
):
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO summaries (
                source_text,
                result_text,
                created_at,
                limit_value,
                mode,
                source_words,
                result_words,
                status,
                error_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_text,
                result_text,
                datetime.now(timezone.utc).isoformat(),
                limit_value,
                mode,
                source_words,
                result_words,
                status,
                error_text,
            ),
        )
        connection.execute(
            """
            DELETE FROM summaries
            WHERE id NOT IN (
                SELECT id FROM summaries
                ORDER BY id DESC
                LIMIT ?
            )
            """,
            (HISTORY_LIMIT,),
        )


def get_history_items():
    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                source_text,
                result_text,
                created_at,
                limit_value,
                mode,
                source_words,
                result_words,
                status,
                error_text
            FROM summaries
            ORDER BY id DESC
            LIMIT ?
            """,
            (HISTORY_LIMIT,),
        ).fetchall()

    return [dict(row) for row in rows]


def clear_history_entries():
    with get_db_connection() as connection:
        connection.execute("DELETE FROM summaries")


def delete_history_entry(history_id: int) -> bool:
    with get_db_connection() as connection:
        cursor = connection.execute("DELETE FROM summaries WHERE id = ?", (history_id,))
        return cursor.rowcount > 0
