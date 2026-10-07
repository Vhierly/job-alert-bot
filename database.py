"""
SQLite database to track sent jobs (avoid duplicates)
"""
import sqlite3
import time
from config import DB_PATH


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS sent_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_key TEXT UNIQUE,
            company TEXT,
            position TEXT,
            source TEXT,
            sent_at REAL
        )
    """)
    conn.commit()
    conn.close()


def is_job_sent(job_key: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM sent_jobs WHERE job_key = ?", (job_key,))
    exists = c.fetchone() is not None
    conn.close()
    return exists


def mark_job_sent(job_key: str, company: str, position: str, source: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO sent_jobs (job_key, company, position, source, sent_at) VALUES (?, ?, ?, ?, ?)",
        (job_key, company, position, source, time.time()),
    )
    conn.commit()
    conn.close()


def cleanup_old_jobs(days=30):
    """Remove entries older than N days to keep DB small."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    cutoff = time.time() - (days * 86400)
    c.execute("DELETE FROM sent_jobs WHERE sent_at < ?", (cutoff,))
    conn.commit()
    conn.close()
