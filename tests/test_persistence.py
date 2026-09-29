from pathlib import Path

from engine.connections import ConnectionRegistry
from engine.secrets import MemorySecretStore
from engine.storage import LocalStore


def test_connection_metadata_and_secret_survive_registry_restart(tmp_path: Path):
    database = tmp_path / "state.sqlite3"
    secrets = MemorySecretStore()
    first = ConnectionRegistry(LocalStore(database), secrets)
    record = first.add("Analytics", "sqlite:///analytics.sqlite", "sqlite")
    first.close()

    reopened = ConnectionRegistry(LocalStore(database), secrets)
    restored = reopened.get(record.id)

    assert restored.public()["name"] == "Analytics"
    assert restored.dialect == "sqlite"
    assert restored.connection_url() == "sqlite:///analytics.sqlite"
    reopened.close()


def test_schema_sync_reports_incremental_changes(tmp_path: Path):
    store = LocalStore(tmp_path / "state.sqlite3")
    registry = ConnectionRegistry(store, MemorySecretStore())
    connection = registry.add("Test", "sqlite:///test.sqlite", "sqlite")
    first = store.replace_schema(connection.id, [{"object_key": "table:users", "object_type": "table", "payload": {"name": "users"}}], "now")
    second = store.replace_schema(connection.id, [{"object_key": "table:users", "object_type": "table", "payload": {"name": "users", "columns": 2}}, {"object_key": "table:orders", "object_type": "table", "payload": {"name": "orders"}}], "later")

    assert first == {"added": 1, "changed": 0, "deleted": 0, "unchanged": 0}
    assert second == {"added": 1, "changed": 1, "deleted": 0, "unchanged": 0}
    registry.close()
