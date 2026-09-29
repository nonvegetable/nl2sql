"""Database adapter contracts and the SQLAlchemy relational implementation."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


class DatabaseAdapter(Protocol):
    def test_connection(self) -> None: ...
    def list_catalogs(self) -> list[str]: ...
    def list_schemas(self) -> list[str]: ...
    def list_tables(self) -> list[str]: ...
    def get_columns(self, table: str) -> list[dict]: ...
    def get_primary_keys(self, table: str) -> list[str]: ...
    def get_foreign_keys(self, table: str) -> list[dict]: ...
    def get_indexes(self, table: str) -> list[dict]: ...
    def get_views(self) -> list[str]: ...
    def execute_query(self, sql: str, max_rows: int) -> dict: ...
    def explain_query(self, sql: str) -> list[dict]: ...


class SQLAlchemyAdapter:
    """Common adapter for SQLite, PostgreSQL, MySQL/MariaDB, and SQL Server."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def test_connection(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def _inspector(self):
        return inspect(self.engine)

    def list_catalogs(self) -> list[str]:
        return []

    def list_schemas(self) -> list[str]:
        return self._inspector().get_schema_names()

    def list_tables(self) -> list[str]:
        return self._inspector().get_table_names()

    def get_columns(self, table: str) -> list[dict]:
        return self._inspector().get_columns(table)

    def get_primary_keys(self, table: str) -> list[str]:
        return self._inspector().get_pk_constraint(table).get("constrained_columns") or []

    def get_foreign_keys(self, table: str) -> list[dict]:
        return self._inspector().get_foreign_keys(table)

    def get_indexes(self, table: str) -> list[dict]:
        return self._inspector().get_indexes(table)

    def get_views(self) -> list[str]:
        return self._inspector().get_view_names()

    def execute_query(self, sql: str, max_rows: int) -> dict:
        with self.engine.connect() as connection:
            result = connection.execute(text(sql))
            rows = result.fetchmany(max_rows)
            return {"columns": list(result.keys()), "rows": [dict(row._mapping) for row in rows], "row_count": len(rows)}

    def explain_query(self, sql: str) -> list[dict]:
        with self.engine.connect() as connection:
            result = connection.execute(text(f"EXPLAIN {sql}"))
            return [dict(row._mapping) for row in result]


SUPPORTED_DIALECTS = {"sqlite", "postgresql", "mysql", "mariadb", "mssql"}
PLANNED_DIALECTS = {"oracle", "bigquery"}
