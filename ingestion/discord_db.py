"""SQLite store for raw Discord messages captured by windows_watcher.py or bot.py.

Separate from paper.db — this is a raw capture buffer.
The live pipeline reads from here and feeds messages into parse -> risk -> broker.

DB path: data/discord_messages.db
"""
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "discord_messages.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id   TEXT    NOT NULL UNIQUE,
                author_id    TEXT    NOT NULL,
                author_name  TEXT    NOT NULL,
                channel_id   TEXT    NOT NULL,
                channel_name TEXT    NOT NULL,
                guild_id     TEXT,
                guild_name   TEXT,
                content      TEXT    NOT NULL,
                created_at   TEXT    NOT NULL,
                saved_at     TEXT    NOT NULL
            )
        """)
        conn.commit()


def save_message(
    message_id: str,
    author_id: str,
    author_name: str,
    channel_id: str,
    channel_name: str,
    guild_id: str | None,
    guild_name: str | None,
    content: str,
    created_at: datetime,
) -> bool:
    """Returns True if inserted, False if duplicate."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO messages
                    (message_id, author_id, author_name, channel_id, channel_name,
                     guild_id, guild_name, content, created_at, saved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    author_id,
                    author_name,
                    channel_id,
                    channel_name,
                    guild_id,
                    guild_name,
                    content,
                    created_at.isoformat(),
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False


def fetch_after(last_id: int, limit: int = 100) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM messages WHERE id > ? ORDER BY id ASC LIMIT ?",
            (last_id, limit),
        ).fetchall()


def fetch_recent(limit: int = 20) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM messages ORDER BY saved_at DESC LIMIT ?", (limit,)
        ).fetchall()
