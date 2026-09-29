"""Persistent database connections with pooled SQLAlchemy engines."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from time import monotonic
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

from engine.adapters import SQLAlchemyAdapter
from engine.secrets import KeyringSecretStore, SecretStore
from engine.security import ValidatedSQL
from engine.storage import LocalStore


@dataclass
class ConnectionRecord:
    id: str
    name: str
    dialect: str
    safe_url: str = field(repr=False)
    secret_key: str | None = field(default=None, repr=False)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    secrets: SecretStore = field(repr=False, compare=False, default_factory=KeyringSecretStore)
    engine: Engine = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.engine = create_engine(self.connection_url(), pool_pre_ping=True, pool_recycle=1800, pool_timeout=30)

    def connection_url(self) -> str:
        if not self.secret_key:
            return self.safe_url
        password = self.secrets.get(self.secret_key)
        return str(make_url(self.safe_url).set(password=password))

    def public(self) -> dict[str, str]:
        return {"id": self.id, "name": self.name, "dialect": self.dialect, "created_at": self.created_at}

    def test(self) -> None:
        SQLAlchemyAdapter(self.engine).test_connection()

    def tables(self) -> list[dict]:
        adapter = SQLAlchemyAdapter(self.engine)
        result = []
        for name in adapter.list_tables():
            columns = adapter.get_columns(name)
            foreign_keys = adapter.get_foreign_keys(name)
            result.append({
                "name": name,
                "columns": [{"name": item["name"], "type": str(item["type"]), "nullable": item.get("nullable", True)} for item in columns],
                "foreign_keys": foreign_keys,
                "primary_keys": adapter.get_primary_keys(name),
                "indexes": adapter.get_indexes(name),
            })
        return result

    def execute(self, query: ValidatedSQL, max_rows: int, max_result_bytes: int = 5_000_000) -> dict:
        started = monotonic()
        with self.engine.connect() as connection:
            result = connection.execute(text(query.sql))
            rows = []
            response_bytes = 0
            for row in result:
                serialized = dict(row._mapping)
                response_bytes += len(repr(serialized).encode("utf-8"))
                if response_bytes > max_result_bytes:
                    break
                rows.append(serialized)
                if len(rows) >= max_rows:
                    break
            return {"columns": list(result.keys()), "rows": rows, "row_count": len(rows), "truncated": response_bytes > max_result_bytes or len(rows) >= max_rows, "latency_ms": round((monotonic() - started) * 1000, 2)}


class ConnectionRegistry:
    def __init__(self, store: LocalStore | None = None, secrets: SecretStore | None = None) -> None:
        self.store = store or LocalStore()
        self.secrets = secrets or KeyringSecretStore()
        self._records: dict[str, ConnectionRecord] = {}
        self._lock = RLock()
        self._load()

    def _load(self) -> None:
        for row in self.store.list_connections():
            record = ConnectionRecord(row["id"], row["name"], row["dialect"], row["safe_url"], row["secret_key"], row["created_at"], self.secrets)
            self._records[record.id] = record

    def add(self, name: str, url: str, dialect: str | None = None) -> ConnectionRecord:
        if not url or "://" not in url:
            raise ValueError("A valid SQLAlchemy connection URL is required.")
        parsed = make_url(url)
        record_id = str(uuid4())
        secret_key = f"connection:{record_id}:password" if parsed.password else None
        safe_url = str(parsed.set(password=None)) if parsed.password else str(parsed)
        if secret_key:
            self.secrets.set(secret_key, parsed.password or "")
        record = ConnectionRecord(record_id, name.strip() or "Database", dialect or parsed.drivername.split("+")[0], safe_url, secret_key, secrets=self.secrets)
        with self._lock:
            self._records[record.id] = record
            self.store.save_connection({"id": record.id, "name": record.name, "dialect": record.dialect, "safe_url": record.safe_url, "secret_key": record.secret_key, "created_at": record.created_at})
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
            if record.secret_key:
                self.secrets.delete(record.secret_key)
            self.store.delete_connection(connection_id)

    def close(self) -> None:
        for record in self.all():
            record.engine.dispose()
        self.store.close()
