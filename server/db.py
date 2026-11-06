import sqlite3
import time
from contextlib import contextmanager


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  openid TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL,
  last_login_at INTEGER NOT NULL,
  disabled INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  share_url TEXT NOT NULL,
  aweme_id TEXT NOT NULL,
  title TEXT NOT NULL,
  kind TEXT NOT NULL,
  item_count INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_user_time ON history(user_id, created_at DESC);
CREATE TABLE IF NOT EXISTS parse_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  aweme_id TEXT,
  success INTEGER NOT NULL,
  message TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_parse_user_time ON parse_events(user_id, created_at DESC);
CREATE TABLE IF NOT EXISTS save_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  history_id INTEGER NOT NULL REFERENCES history(id) ON DELETE CASCADE,
  item_index INTEGER NOT NULL,
  media_kind TEXT NOT NULL,
  success INTEGER NOT NULL,
  message TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_save_user_time ON save_events(user_id, created_at DESC);
CREATE TABLE IF NOT EXISTS admin_sessions (
  token_hash TEXT PRIMARY KEY,
  csrf_hash TEXT NOT NULL,
  expires_at INTEGER NOT NULL
);
"""


class Database:
    def __init__(self, path):
        self.path = str(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def prune(self):
        now = int(time.time())
        with self.connect() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
            conn.execute("DELETE FROM admin_sessions WHERE expires_at < ?", (now,))
            conn.execute("DELETE FROM history WHERE created_at < ?", (now - 30 * 86400,))
            conn.execute("DELETE FROM parse_events WHERE created_at < ?", (now - 30 * 86400,))
            conn.execute("DELETE FROM save_events WHERE created_at < ?", (now - 30 * 86400,))
