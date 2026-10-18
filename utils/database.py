import sqlite3
import os
import logging

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

    conn.commit()
    conn.close()
    logger.info("✅ تم تهيئة قاعدة البيانات بنجاح")


def save_user(user_id, username, first_name):
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


def get_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_level(user_id, level):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET level = ? WHERE user_id = ?", (level, user_id))
    conn.commit()
    conn.close()


def get_user_stats(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return None

    cursor.execute("""
        SELECT level, COUNT(*) as count, SUM(score) as total
        FROM progress WHERE user_id = ? GROUP BY level
    """, (user_id,))
    by_level = {row["level"]: {"count": row["count"], "score": row["total"]} for row in cursor.fetchall()}

    cursor.execute("""
        SELECT lesson_topic, score, completed_at FROM progress
        WHERE user_id = ? ORDER BY completed_at DESC LIMIT 5
    """, (user_id,))
    recent = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return {"user": dict(user), "by_level": by_level, "recent_lessons": recent}


def save_progress(user_id, lesson_topic, level, score):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO progress (user_id, lesson_topic, level, score)
        VALUES (?, ?, ?, ?)
    """, (user_id, lesson_topic, level, score))
    cursor.execute("""
        UPDATE users SET current_lesson = current_lesson + 1,
            total_score = total_score + ?, last_active = CURRENT_TIMESTAMP
        WHERE user_id = ?
    """, (score, user_id))
    conn.commit()
    conn.close()


def save_level_test(user_id, score, assigned_level):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO level_tests (user_id, score, assigned_level)
        VALUES (?, ?, ?)
    """, (user_id, score, assigned_level))
    conn.commit()
    conn.close()
