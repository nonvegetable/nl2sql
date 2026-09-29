import pytest

from engine.security import SQLSecurityError, validate_read_query


def test_select_is_normalized_and_bounded():
    result = validate_read_query("select id from customers", dialect="sqlite", max_rows=25)

    assert "LIMIT 25" in result.sql.upper()
    assert result.tables == ("customers",)


@pytest.mark.parametrize(
    "query",
    [
        "DROP TABLE customers",
        "DELETE FROM customers",
        "UPDATE customers SET name = 'x'",
        "SELECT * FROM customers; DELETE FROM customers",
    ],
)
def test_mutating_and_multiple_statements_are_rejected(query):
    with pytest.raises(SQLSecurityError):
        validate_read_query(query, dialect="sqlite")


def test_existing_limit_is_preserved():
    result = validate_read_query("SELECT * FROM customers LIMIT 5", dialect="sqlite", max_rows=25)

    assert "LIMIT 5" in result.sql.upper()
    assert "LIMIT 25" not in result.sql.upper()


@pytest.mark.parametrize("query", [
    "WITH recent AS (SELECT id FROM customers) SELECT * FROM recent",
    "SELECT id FROM customers UNION SELECT id FROM archived_customers",
    "SELECT id FROM customers INTERSECT SELECT id FROM archived_customers",
    "SELECT id FROM customers EXCEPT SELECT id FROM archived_customers",
])
def test_read_only_set_operations_are_allowed(query):
    assert validate_read_query(query, dialect="sqlite").sql


@pytest.mark.parametrize("query", [
    "CREATE TABLE users (id INT)",
    "ALTER TABLE users ADD COLUMN email TEXT",
    "GRANT SELECT ON users TO analyst",
    "REVOKE SELECT ON users FROM analyst",
    "EXECUTE dangerous_proc()",
    "SELECT 1 /* ; DROP TABLE users */",
])
def test_unsafe_statements_and_comment_tricks_are_rejected(query):
    with pytest.raises(SQLSecurityError):
        validate_read_query(query, dialect="sqlite")
