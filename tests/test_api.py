from fastapi.testclient import TestClient

from engine.api import app, history, registry


def setup_function():
    history.clear()
    for record in registry.all():
        registry.remove(record.id)


def test_health_and_validate_endpoint():
    client = TestClient(app)

    assert client.get("/api/v1/health").json()["status"] == "ok"
    response = client.post("/api/v1/query/validate", json={"sql": "SELECT 1", "dialect": "sqlite", "max_rows": 5})

    assert response.status_code == 200
    assert "LIMIT 5" in response.json()["sql"].upper()


def test_sql_injection_is_rejected_before_connection_lookup():
    client = TestClient(app)
    response = client.post("/api/v1/query/validate", json={"sql": "SELECT 1; DROP TABLE users", "dialect": "sqlite"})

    assert response.status_code == 422


def test_unknown_query_returns_not_found():
    client = TestClient(app)

    assert client.get("/api/v1/query/missing").status_code == 404
