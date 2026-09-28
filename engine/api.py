"""Versioned local HTTP API for the desktop runtime."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from engine.connections import ConnectionRegistry
from engine.security import SQLSecurityError, validate_read_query


class ConnectionCreate(BaseModel):
    name: str = Field(default="Database", min_length=1, max_length=120)
    url: str = Field(min_length=10)
    dialect: str | None = None


class QueryValidate(BaseModel):
    sql: str
    dialect: str = "postgres"
    max_rows: int = Field(default=1000, ge=1, le=100000)


class QueryRequest(QueryValidate):
    connection_id: str


registry = ConnectionRegistry()
history: list[dict[str, Any]] = []
app = FastAPI(title="NL2SQL Engine", version="1.0.0", docs_url="/api/docs", redoc_url=None)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "engine": "nl2sql"}


@app.get("/api/v1/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/api/v1/connections", status_code=201)
def create_connection(payload: ConnectionCreate) -> dict:
    try:
        return registry.add(payload.name, payload.url, payload.dialect).public()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/connections")
def list_connections() -> list[dict]:
    return [record.public() for record in registry.all()]


@app.get("/api/v1/connections/{connection_id}")
def get_connection(connection_id: str) -> dict:
    try:
        return registry.get(connection_id).public()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/v1/connections/{connection_id}", status_code=204)
def delete_connection(connection_id: str) -> None:
    try:
        registry.remove(connection_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/connections/{connection_id}/test")
def test_connection(connection_id: str) -> dict[str, str]:
    try:
        registry.get(connection_id).test()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Database connection failed.") from exc
    return {"status": "ok"}


@app.get("/api/v1/connections/{connection_id}/tables")
def get_tables(connection_id: str) -> list[dict]:
    try:
        return registry.get(connection_id).tables()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Schema inspection failed.") from exc


@app.get("/api/v1/connections/{connection_id}/schema")
def get_schema(connection_id: str) -> dict:
    return {"connection_id": connection_id, "tables": get_tables(connection_id)}


@app.post("/api/v1/connections/{connection_id}/sync")
def sync_schema(connection_id: str) -> dict:
    """Discover the current schema; indexing backends can consume this result."""
    tables = get_tables(connection_id)
    return {"connection_id": connection_id, "status": "synced", "table_count": len(tables), "tables": tables}


@app.post("/api/v1/query/validate")
def validate_query(payload: QueryValidate) -> dict:
    try:
        result = validate_read_query(payload.sql, dialect=payload.dialect, max_rows=payload.max_rows)
    except (SQLSecurityError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"sql": result.sql, "dialect": result.dialect, "tables": result.tables}


@app.post("/api/v1/query")
def execute_query(payload: QueryRequest) -> dict:
    try:
        connection = registry.get(payload.connection_id)
        validated = validate_read_query(payload.sql, dialect=payload.dialect, max_rows=payload.max_rows)
        result = connection.execute(validated, payload.max_rows)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (SQLSecurityError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Query execution failed.") from exc

    query_id = str(uuid4())
    history.append({
        "id": query_id,
        "connection_id": payload.connection_id,
        "sql": validated.sql,
        "dialect": validated.dialect,
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"id": query_id, "sql": validated.sql, **result}


@app.get("/api/v1/query/{query_id}")
def get_query(query_id: str) -> dict:
    for item in history:
        if item["id"] == query_id:
            return item
    raise HTTPException(status_code=404, detail="Query not found.")


@app.get("/api/v1/history")
def get_history() -> list[dict]:
    return list(reversed(history))


def create_app() -> FastAPI:
    return app
