"""Database connection registry and adapter-shaped SQLAlchemy access."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from engine.security import ValidatedSQL


@dataclass
class ConnectionRecord:
    id: str
    name: str
    dialect: str
    url: str = field(repr=False)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    engine: Engine = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.engine = create_engine(
            self.url,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_timeout=30,
        )

    def public(self) -> dict[str, str]:
        return {"id": self.id, "name": self.name, "dialect": self.dialect, "created_at": self.created_at}

    def test(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def tables(self) -> list[dict]:
        inspector = inspect(self.engine)
        result = []
        for name in inspector.get_table_names():
            columns = inspector.get_columns(name)
            foreign_keys = inspector.get_foreign_keys(name)
            result.append({
                "name": name,
                "columns": [{"name": item["name"], "type": str(item["type"]), "nullable": item.get("nullable", True)} for item in columns],
                "foreign_keys": foreign_keys,
            })
        return result

    def execute(self, query: ValidatedSQL, max_rows: int) -> dict:
        with self.engine.connect() as connection:
            result = connection.execute(text(query.sql))
            rows = result.fetchmany(max_rows)
            return {"columns": list(result.keys()), "rows": [dict(row._mapping) for row in rows], "row_count": len(rows)}


class ConnectionRegistry:
    def __init__(self) -> None:
        self._records: dict[str, ConnectionRecord] = {}
        self._lock = RLock()

    def add(self, name: str, url: str, dialect: str | None = None) -> ConnectionRecord:
        if not url or "://" not in url:
            raise ValueError("A valid SQLAlchemy connection URL is required.")
        record = ConnectionRecord(id=str(uuid4()), name=name.strip() or "Database", dialect=dialect or url.split(":", 1)[0], url=url)
        with self._lock:
            self._records[record.id] = record
        return record

    def get(self, connection_id: str) -> ConnectionRecord:
        with self._lock:
            try:
                return self._records[connection_id]
            except KeyError as exc:
                raise KeyError(f"Unknown connection: {connection_id}") from exc

    def all(self) -> list[ConnectionRecord]:
        with self._lock:
            return list(self._records.values())

    def remove(self, connection_id: str) -> None:
        with self._lock:
            record = self._records.pop(connection_id)
            record.engine.dispose()
