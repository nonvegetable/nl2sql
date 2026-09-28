"""SQL parsing and read-only execution guardrails."""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError


class SQLSecurityError(ValueError):
    """Raised when generated SQL is unsafe to execute."""


@dataclass(frozen=True)
class ValidatedSQL:
    sql: str
    dialect: str
    tables: tuple[str, ...]


_READ_STATEMENTS = (exp.Select, exp.Union, exp.Intersect, exp.Except, exp.With)


def _table_names(expression: exp.Expression) -> tuple[str, ...]:
    names = []
    for table in expression.find_all(exp.Table):
        name = table.sql(dialect="")
        if name not in names:
            names.append(name)
    return tuple(names)


def validate_read_query(
    sql: str,
    *,
    dialect: str = "postgres",
    max_rows: int = 1000,
) -> ValidatedSQL:
    """Parse and validate a single bounded read query.

    SQL is never executed before this function succeeds. The limit is applied
    only when the query has no existing LIMIT so callers cannot accidentally
    materialize an unbounded result set.
    """
    candidate = (sql or "").strip().rstrip(";").strip()
    if not candidate:
        raise SQLSecurityError("SQL query is empty.")
    if max_rows < 1:
        raise ValueError("max_rows must be greater than zero.")

    try:
        statements = sqlglot.parse(candidate, read=dialect)
    except ParseError as exc:
        raise SQLSecurityError(f"SQL could not be parsed: {exc}") from exc
    if len(statements) != 1:
        raise SQLSecurityError("Multiple SQL statements are not allowed.")

    expression = statements[0]
    if not isinstance(expression, _READ_STATEMENTS):
        raise SQLSecurityError("Only read-only SELECT statements are allowed.")
    if any(list(expression.find_all(node)) for node in (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create)):
        raise SQLSecurityError("The query contains a mutating or DDL statement.")

    bounded = expression if expression.args.get("limit") else expression.limit(max_rows)
    normalized = bounded.sql(dialect=dialect)
    return ValidatedSQL(sql=normalized, dialect=dialect, tables=_table_names(expression))
