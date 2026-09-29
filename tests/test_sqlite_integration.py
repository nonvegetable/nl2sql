from pathlib import Path

from sqlalchemy import create_engine, text

from engine.connections import ConnectionRegistry
from engine.security import validate_read_query
from engine.secrets import MemorySecretStore
from engine.storage import LocalStore


def test_sqlite_connection_schema_sync_and_bounded_execution(tmp_path: Path):
    database = tmp_path / "analytics.sqlite3"
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"))
        connection.execute(text("INSERT INTO users VALUES (1, 'Ada'), (2, 'Grace')"))

    registry = ConnectionRegistry(LocalStore(tmp_path / "state.sqlite3"), MemorySecretStore())
    record = registry.add("Analytics", f"sqlite:///{database}", "sqlite")
    tables = record.tables()
    query = validate_read_query("SELECT id, name FROM users", dialect="sqlite", max_rows=1)
    result = record.execute(query, 1)

    assert tables[0]["name"] == "users"
    assert tables[0]["primary_keys"] == ["id"]
    assert result["row_count"] == 1
    assert result["rows"][0]["name"] == "Ada"
    registry.close()
