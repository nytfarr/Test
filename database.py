import sqlite3

DB_PATH = "work_tracker.db"


def init_db():
    """Initialize the database and create the users table if it doesn't exist."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id   INTEGER PRIMARY KEY,
                total_work INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()


def ensure_user(user_id: int):
    """Insert a new user row if one doesn't already exist."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR IGNORE INTO users (user_id, total_work)
            VALUES (?, 0)
        """, (user_id,))
        conn.commit()


def increment_work(user_id: int):
    """Add 1 to the user's total work count."""
    ensure_user(user_id)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            UPDATE users
            SET total_work = total_work + 1
            WHERE user_id = ?
        """, (user_id,))
        conn.commit()


def get_total_work(user_id: int) -> int:
    """Return the user's total completed work count."""
    ensure_user(user_id)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("""
            SELECT total_work FROM users WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        return row[0] if row else 0
      
