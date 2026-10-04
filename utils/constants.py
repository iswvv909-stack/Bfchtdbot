import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "english_bot.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            level TEXT DEFAULT 'beginner',
            current_lesson INTEGER DEFAULT 0,
            total_score INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            lesson_topic TEXT NOT NULL,
            level TEXT,
            score INTEGER DEFAULT 0,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS level_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            assigned_level TEXT NOT NULL,
            taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_user ON progress(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_date ON progress(completed_at)")

    conn.commit()
    conn.close()
    logger.info("✅ تم تهيئة قاعدة البيانات بنجاح")


def save_user(user_id: int, username: str, first_name: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            last_active = CURRENT_TIMESTAMP
    """, (user_id, username, first_name))
    conn.commit()
    conn.close()


def get_user(user_id: int) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_level(user_id: int, level: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET level = ? WHERE user_id = ?", (level, user_id))
    conn.commit()
    conn.close()


def get_user_stats(user_id: int) -> dict:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return None

    cursor.execute("""
        SELECT level, COUNT(*) as count, SUM(score) as total
        FROM progress
        WHERE user_id = ?
        GROUP BY level
    """, (user_id,))
    by_level = {row["level"]: {"count": row["count"], "score": row["total"]} for row in cursor.fetchall()}

    cursor.execute("""
        SELECT lesson_topic, score, completed_at
        FROM progress
        WHERE user_id = ?
        ORDER BY completed_at DESC
        LIMIT 5
    """, (user_id,))
    recent = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return {
        "user": dict(user),
        "by_level": by_level,
        "recent_lessons": recent,
    }


def save_progress(user_id: int, lesson_topic: str, level: str, score: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO progress (user_id, lesson_topic, level, score)
        VALUES (?, ?, ?, ?)
    """, (user_id, lesson_topic, level, score))

    cursor.execute("""
        UPDATE users 
        SET current_lesson = current_lesson + 1,
            total_score = total_score + ?,
            last_active = CURRENT_TIMESTAMP
        WHERE user_id = ?
    """, (score, user_id))

    conn.commit()
    conn.close()


def get_progress_count(user_id: int) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as c FROM progress WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()["c"]
    conn.close()
    return count


def get_lessons_by_topic(user_id: int, topic: str) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM progress 
        WHERE user_id = ? AND lesson_topic = ?
        ORDER BY completed_at DESC
    """, (user_id, topic))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def save_level_test(user_id: int, score: int, assigned_level: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO level_tests (user_id, score, assigned_level)
        VALUES (?, ?, ?)
    """, (user_id, score, assigned_level))
    conn.commit()
    conn.close()


def get_last_level_test(user_id: int) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM level_tests 
        WHERE user_id = ?
        ORDER BY taken_at DESC
        LIMIT 1
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_top_users(limit: int = 10) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, first_name, total_score, current_lesson
        FROM users
        ORDER BY total_score DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_total_users() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as c FROM users")
    count = cursor.fetchone()["c"]
    conn.close()
    return count


def delete_user(user_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def reset_user_progress(user_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM progress WHERE user_id = ?", (user_id,))
    cursor.execute("""
        UPDATE users 
        SET current_lesson = 0, total_score = 0
        WHERE user_id = ?
    """, (user_id,))
    conn.commit()
    conn.close()
