"""Local SQLite persistence for non-secret engine state."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from platformdirs import user_data_dir


def default_data_dir() -> Path:
    configured = os.getenv("NL2SQL_DATA_DIR")
    return Path(configured).expanduser() if configured else Path(user_data_dir("NL2SQL", "nonvegetable"))


class LocalStore:
    def __init__(self, path: str | Path | None = None) -> None:
        target = Path(path) if path else default_data_dir() / "nl2sql.sqlite3"
        if target != Path(":memory:"):
            target.parent.mkdir(parents=True, exist_ok=True)
        self.path = target
        self.connection = sqlite3.connect(str(target), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS connections (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                dialect TEXT NOT NULL,
                safe_url TEXT NOT NULL,
                secret_key TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS query_history (
                id TEXT PRIMARY KEY,
                question TEXT,
                sql TEXT NOT NULL,
                connection_id TEXT NOT NULL,
                dialect TEXT NOT NULL,
                model TEXT,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                latency_ms REAL,
                error_category TEXT,
                error_message TEXT,
                FOREIGN KEY(connection_id) REFERENCES connections(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS schema_objects (
                connection_id TEXT NOT NULL,
                object_key TEXT NOT NULL,
                object_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(connection_id, object_key),
                FOREIGN KEY(connection_id) REFERENCES connections(id) ON DELETE CASCADE
            );
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def save_connection(self, record: dict[str, str]) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO connections(id, name, dialect, safe_url, secret_key, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            tuple(record[key] for key in ("id", "name", "dialect", "safe_url", "secret_key", "created_at")),
        )
        self.connection.commit()

    def list_connections(self) -> list[sqlite3.Row]:
        return list(self.connection.execute("SELECT * FROM connections ORDER BY created_at"))

    def get_connection(self, connection_id: str) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM connections WHERE id = ?", (connection_id,)).fetchone()

    def delete_connection(self, connection_id: str) -> None:
        self.connection.execute("DELETE FROM connections WHERE id = ?", (connection_id,))
        self.connection.commit()

    def save_history(self, item: dict) -> None:
        columns = ("id", "question", "sql", "connection_id", "dialect", "model", "timestamp", "status", "latency_ms", "error_category", "error_message")
        self.connection.execute(
            f"INSERT OR REPLACE INTO query_history({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
            tuple(item.get(column) for column in columns),
        )
        self.connection.commit()

    def get_history(self, query_id: str | None = None) -> list[sqlite3.Row]:
        if query_id:
            row = self.connection.execute("SELECT * FROM query_history WHERE id = ?", (query_id,)).fetchone()
            return [row] if row else []
        return list(self.connection.execute("SELECT * FROM query_history ORDER BY timestamp DESC"))

    def clear_history(self) -> None:
        self.connection.execute("DELETE FROM query_history")
        self.connection.commit()

    def replace_schema(self, connection_id: str, objects: list[dict], timestamp: str) -> dict[str, int]:
        existing = {row["object_key"]: row["fingerprint"] for row in self.connection.execute("SELECT object_key, fingerprint FROM schema_objects WHERE connection_id = ?", (connection_id,))}
        incoming = {}
        added = changed = 0
        for item in objects:
            key = item["object_key"]
            fingerprint = hashlib.sha256(json.dumps(item["payload"], sort_keys=True).encode()).hexdigest()
            incoming[key] = fingerprint
            if key not in existing:
                added += 1
            elif existing[key] != fingerprint:
                changed += 1
            self.connection.execute(
                "INSERT OR REPLACE INTO schema_objects(connection_id, object_key, object_type, payload, fingerprint, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (connection_id, key, item["object_type"], json.dumps(item["payload"], sort_keys=True), fingerprint, timestamp),
            )
        deleted = len(set(existing) - set(incoming))
        if deleted:
            placeholders = ",".join("?" for _ in set(existing) - set(incoming))
            self.connection.execute(f"DELETE FROM schema_objects WHERE connection_id = ? AND object_key IN ({placeholders})", (connection_id, *set(existing) - set(incoming)))
        self.connection.commit()
        return {"added": added, "changed": changed, "deleted": deleted, "unchanged": len(existing) - changed - deleted}

    def schema(self, connection_id: str) -> list[dict]:
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in self.connection.execute("SELECT * FROM schema_objects WHERE connection_id = ? ORDER BY object_key", (connection_id,))]
