"""Connection-scoped hybrid schema retrieval over persisted schema objects."""

from __future__ import annotations

import re
from collections import deque

from engine.storage import LocalStore


class SchemaRetriever:
    def __init__(self, store: LocalStore) -> None:
        self.store = store

    def search(self, connection_id: str, question: str, limit: int = 8) -> list[dict]:
        objects = self.store.schema(connection_id)
        terms = {term.lower() for term in re.findall(r"[A-Za-z_][A-Za-z0-9_]+", question)}
        scored: list[tuple[int, dict]] = []
        for item in objects:
            payload = item["payload"]
            text = str(payload).lower()
            lexical = sum(2 for term in terms if term in text)
            metadata = 1 if any(term == str(payload.get("name", "")).lower() for term in terms) else 0
            if lexical or metadata:
                scored.append((lexical + metadata, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        selected = [item for _, item in scored[:limit]]

        selected_keys = {item["object_key"] for item in selected}
        queue = deque(selected)
        while queue:
            item = queue.popleft()
            for foreign_key in item["payload"].get("foreign_keys", []):
                referred = foreign_key.get("referred_table")
                key = f"table:{referred}"
                if referred and key not in selected_keys:
                    match = next((candidate for candidate in objects if candidate["object_key"] == key), None)
                    if match:
                        selected.append(match)
                        selected_keys.add(key)
        return selected[:limit]
