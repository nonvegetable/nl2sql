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
