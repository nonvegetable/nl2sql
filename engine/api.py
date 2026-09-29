"""Versioned local HTTP API for the desktop runtime."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from engine.connections import ConnectionRegistry
from engine.llm import ExistingProviders, LLMProvider
from engine.retrieval import SchemaRetriever
from engine.security import SQLSecurityError, validate_read_query


class ConnectionCreate(BaseModel):
    name: str = Field(default="Database", min_length=1, max_length=120)
    url: str | None = Field(default=None, min_length=10)
    dialect: str | None = None
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    database: str | None = None
    schema_: str | None = Field(default=None, alias="schema")
    username: str | None = None
    password: str | None = None
    ssl: bool = False


def _connection_url(payload: ConnectionCreate) -> str:
    if payload.url:
        return payload.url
    dialect = (payload.dialect or "").lower()
    if dialect == "sqlite":
        if not payload.database:
            raise ValueError("SQLite requires a database path.")
        return f"sqlite:///{payload.database}"
    if dialect not in {"postgresql", "mysql", "mariadb", "mssql", "oracle", "bigquery"}:
        raise ValueError("Choose a supported database type or provide an advanced connection URL.")
    if not payload.host or not payload.database:
        raise ValueError("Host and database are required.")
    driver = {"postgresql": "postgresql+psycopg2", "mysql": "mysql+pymysql", "mariadb": "mariadb+pymysql", "mssql": "mssql+pyodbc", "oracle": "oracle+oracledb", "bigquery": "bigquery"}[dialect]
    credentials = ""
    if payload.username:
        credentials = quote_plus(payload.username)
        if payload.password:
            credentials += f":{quote_plus(payload.password)}"
        credentials += "@"
    port = f":{payload.port}" if payload.port else ""
    query = "?sslmode=require" if payload.ssl and dialect == "postgresql" else ""
    return f"{driver}://{credentials}{payload.host}{port}/{quote_plus(payload.database)}{query}"


class QueryValidate(BaseModel):
    sql: str
    dialect: str = "postgres"
    max_rows: int = Field(default=1000, ge=1, le=100000)


MAX_RESULT_BYTES = 5_000_000


class QueryRequest(QueryValidate):
    connection_id: str
    question: str | None = None


class QueryGenerate(BaseModel):
    connection_id: str
    question: str = Field(min_length=1, max_length=4000)
    dialect: str = "postgres"
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None


registry = ConnectionRegistry()
history: list[dict[str, Any]] = []
app = FastAPI(title="NL2SQL Engine", version="1.0.0", docs_url="/api/docs", redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "http://127.0.0.1:1420", "tauri://localhost"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "engine": "nl2sql"}


@app.get("/api/v1/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/api/v1/connections", status_code=201)
def create_connection(payload: ConnectionCreate) -> dict:
    try:
        return registry.add(payload.name, _connection_url(payload), payload.dialect).public()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Connection configuration could not be saved.") from exc


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
    """Discover and fingerprint the current schema for incremental sync."""
    try:
        connection = registry.get(connection_id)
        tables = connection.tables()
        objects = [{"object_key": f"table:{table['name']}", "object_type": "table", "payload": table} for table in tables]
        changes = registry.store.replace_schema(connection_id, objects, datetime.now(timezone.utc).isoformat())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Schema synchronization failed.") from exc
    return {"connection_id": connection_id, "status": "synced", "table_count": len(tables), "changes": changes, "tables": tables}


@app.post("/api/v1/query/validate")
def validate_query(payload: QueryValidate) -> dict:
    try:
        result = validate_read_query(payload.sql, dialect=payload.dialect, max_rows=payload.max_rows)
    except (SQLSecurityError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"sql": result.sql, "dialect": result.dialect, "tables": result.tables}


def generate_query(payload: QueryGenerate, llm: LLMProvider | None = None) -> dict:
    try:
        registry.get(payload.connection_id)
        context = SchemaRetriever(registry.store).search(payload.connection_id, payload.question)
        if not context:
            raise ValueError("No synchronized schema matched this question.")
        schema_text = "\n".join(str(item["payload"]) for item in context)
        system_prompt = (
            f"You generate read-only {payload.dialect} SQL. Return only SQL, no markdown or explanation. "
            "Use exactly one SELECT statement and never use INSERT, UPDATE, DELETE, DDL, or multiple statements."
        )
        user_prompt = f"Schema context:\n{schema_text}\n\nQuestion: {payload.question}"
        raw_sql = (llm or ExistingProviders(payload.provider)).generate(system_prompt, user_prompt, model=payload.model, api_key=payload.api_key)
        validated = validate_read_query(raw_sql, dialect=payload.dialect)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (SQLSecurityError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="SQL generation failed.") from exc
    return {"sql": validated.sql, "dialect": validated.dialect, "tables": validated.tables}


@app.post("/api/v1/query/generate")
def generate_query_endpoint(payload: QueryGenerate) -> dict:
    return generate_query(payload)


@app.post("/api/v1/query")
def execute_query(payload: QueryRequest) -> dict:
    try:
        connection = registry.get(payload.connection_id)
        validated = validate_read_query(payload.sql, dialect=payload.dialect, max_rows=payload.max_rows)
        result = connection.execute(validated, payload.max_rows, MAX_RESULT_BYTES)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (SQLSecurityError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Query execution failed.") from exc

    query_id = str(uuid4())
    history_item = {
        "id": query_id,
        "question": payload.question if hasattr(payload, "question") else None,
        "connection_id": payload.connection_id,
        "sql": validated.sql,
        "dialect": validated.dialect,
        "model": None,
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "latency_ms": result.get("latency_ms"),
        "error_category": None,
        "error_message": None,
    }
    history.append(history_item)
    registry.store.save_history(history_item)
    return {"id": query_id, "sql": validated.sql, **result}


@app.get("/api/v1/query/{query_id}")
def get_query(query_id: str) -> dict:
    items = registry.store.get_history(query_id)
    if items:
        return dict(items[0])
    raise HTTPException(status_code=404, detail="Query not found.")


@app.get("/api/v1/history")
def get_history() -> list[dict]:
    return [dict(item) for item in registry.store.get_history()]


def create_app() -> FastAPI:
    return app
