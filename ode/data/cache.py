"""SQLite TTL cache for web fetches and computed results."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


class Cache:
    """Simple SQLite-backed cache with TTL."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            from ..core.store import _project_root
            db_path = _project_root() / "data" / "cache.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at)")

    def get(self, key: str) -> dict | None:
        """Get a cached value. Returns None if missing or expired."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value FROM cache WHERE key = ? AND expires_at > ?",
                (key, time.time()),
            ).fetchone()
        if row:
            return json.loads(row[0])
        return None

    def set(self, key: str, value: dict, ttl_seconds: int = 3600):
        """Set a cache entry with TTL in seconds."""
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (key, json.dumps(value, ensure_ascii=False), now + ttl_seconds, now),
            )

    def delete(self, key: str):
        """Delete a cache entry."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))

    def cleanup(self):
        """Remove all expired entries."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache WHERE expires_at <= ?", (time.time(),))

    def clear(self):
        """Clear all cache entries."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache")

    def stats(self) -> dict:
        """Return cache statistics."""
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            valid = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE expires_at > ?", (now,)
            ).fetchone()[0]
        return {"total": total, "valid": valid, "expired": total - valid}
