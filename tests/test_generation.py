from engine.api import QueryGenerate, generate_query, registry
from engine.llm import LLMProvider


class FakeLLM:
    def generate(self, system_prompt: str, user_prompt: str, *, model=None, api_key=None) -> str:
        assert "sqlite" in system_prompt
        assert "users" in user_prompt
        return "SELECT id, name FROM users"


def test_generation_uses_connection_scoped_schema_and_validates_sql():
    for record in registry.all():
        registry.remove(record.id)
    connection = registry.add("Test", "sqlite:///generation.sqlite", "sqlite")
    registry.store.replace_schema(
        connection.id,
        [{"object_key": "table:users", "object_type": "table", "payload": {"name": "users", "columns": [{"name": "id"}, {"name": "name"}]}}],
        "now",
    )

    result = generate_query(QueryGenerate(connection_id=connection.id, question="List users", dialect="sqlite"), FakeLLM())

    assert result["tables"] == ("users",)
    assert "LIMIT" in result["sql"].upper()
    registry.remove(connection.id)
