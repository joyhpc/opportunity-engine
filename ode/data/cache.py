"""SQLite TTL cache for web fetches and computed results."""

from __future__ import annotations

import json
import time
from pathlib import Path

try:
    import sqlite3
except ImportError:  # pragma: no cover - depends on host Python build
    sqlite3 = None  # type: ignore[assignment]


class Cache:
    """Simple cache with TTL.

    SQLite is used when the host Python build provides it. Some stripped-down
    Windows Python installs miss the `_sqlite3` extension, so a JSON file
    backend keeps the service and tests usable in that environment.
    """

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            from ..core.store import _project_root
            db_path = _project_root() / "data" / "cache.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._json_path = self.db_path.with_suffix(self.db_path.suffix + ".json")
        self._init_db()

    def _init_db(self):
        if sqlite3 is None:
            if not self._json_path.exists():
                self._write_json_store({})
            return
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
        if sqlite3 is None:
            store = self._read_json_store()
            row = store.get(key)
            if not row:
                return None
            if row["expires_at"] <= time.time():
                store.pop(key, None)
                self._write_json_store(store)
                return None
            return row["value"]

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
        if sqlite3 is None:
            store = self._read_json_store()
            store[key] = {"value": value, "expires_at": now + ttl_seconds, "created_at": now}
            self._write_json_store(store)
            return

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (key, json.dumps(value, ensure_ascii=False), now + ttl_seconds, now),
            )

    def delete(self, key: str):
        """Delete a cache entry."""
        if sqlite3 is None:
            store = self._read_json_store()
            store.pop(key, None)
            self._write_json_store(store)
            return

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))

    def cleanup(self):
        """Remove all expired entries."""
        if sqlite3 is None:
            now = time.time()
            store = {key: row for key, row in self._read_json_store().items() if row["expires_at"] > now}
            self._write_json_store(store)
            return

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache WHERE expires_at <= ?", (time.time(),))

    def clear(self):
        """Clear all cache entries."""
        if sqlite3 is None:
            self._write_json_store({})
            return

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache")

    def stats(self) -> dict:
        """Return cache statistics."""
        now = time.time()
        if sqlite3 is None:
            store = self._read_json_store()
            total = len(store)
            valid = sum(1 for row in store.values() if row["expires_at"] > now)
            return {"total": total, "valid": valid, "expired": total - valid}

        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            valid = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE expires_at > ?", (now,)
            ).fetchone()[0]
        return {"total": total, "valid": valid, "expired": total - valid}

    def _read_json_store(self) -> dict:
        if not self._json_path.exists():
            return {}
        return json.loads(self._json_path.read_text(encoding="utf-8") or "{}")

    def _write_json_store(self, store: dict):
        self._json_path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
