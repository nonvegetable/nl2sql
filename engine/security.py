"""SQL parsing and read-only execution guardrails."""

from __future__ import annotations

from dataclasses import dataclass
import re

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
_FORBIDDEN_EXPRESSIONS = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create, exp.Grant, exp.Revoke, exp.Execute, exp.Command, exp.Set)
_SUSPICIOUS_COMMENT = re.compile(r"(?:--[^\n]*|/\*.*?\*/)", re.DOTALL)
_MUTATING_WORD = re.compile(r"\b(?:insert|update|delete|drop|alter|create|truncate|grant|revoke|execute|exec)\b", re.IGNORECASE)


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
    for comment in _SUSPICIOUS_COMMENT.findall(candidate):
        if _MUTATING_WORD.search(comment):
            raise SQLSecurityError("Comments contain a forbidden mutation keyword.")

    try:
        statements = sqlglot.parse(candidate, read=dialect)
    except ParseError as exc:
        raise SQLSecurityError(f"SQL could not be parsed: {exc}") from exc
    if len(statements) != 1:
        raise SQLSecurityError("Multiple SQL statements are not allowed.")

    expression = statements[0]
    if not isinstance(expression, _READ_STATEMENTS):
        raise SQLSecurityError("Only read-only SELECT statements are allowed.")
    if any(list(expression.find_all(node)) for node in _FORBIDDEN_EXPRESSIONS):
        raise SQLSecurityError("The query contains a mutating or DDL statement.")

    bounded = expression if expression.args.get("limit") else expression.limit(max_rows)
    normalized = bounded.sql(dialect=dialect)
    return ValidatedSQL(sql=normalized, dialect=dialect, tables=_table_names(expression))
