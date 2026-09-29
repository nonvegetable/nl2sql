"""Vector-store contract with a connection-scoped Chroma implementation."""

from __future__ import annotations

from typing import Protocol


class VectorStore(Protocol):
    def upsert(self, connection_id: str, records: list[dict]) -> None: ...
    def search(self, connection_id: str, query: str, limit: int = 8) -> list[dict]: ...
    def delete(self, connection_id: str, ids: list[str]) -> None: ...
    def count(self, connection_id: str) -> int: ...
    def health(self) -> bool: ...


class ChromaVectorStore:
    def __init__(self, path: str = "./chroma_db", collection_name: str = "database_schema_metadata") -> None:
        import chromadb
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(collection_name)

    def upsert(self, connection_id: str, records: list[dict]) -> None:
        self.collection.upsert(
            ids=[f"{connection_id}:{record['id']}" for record in records],
            documents=[record["document"] for record in records],
            metadatas=[{**record.get("metadata", {}), "connection_id": connection_id} for record in records],
        )

    def search(self, connection_id: str, query: str, limit: int = 8) -> list[dict]:
        result = self.collection.query(query_texts=[query], n_results=limit, where={"connection_id": connection_id})
        return [{"id": item_id, "document": document, "metadata": metadata} for item_id, document, metadata in zip(result["ids"][0], result["documents"][0], result["metadatas"][0])]

    def delete(self, connection_id: str, ids: list[str]) -> None:
        self.collection.delete(ids=[f"{connection_id}:{item_id}" for item_id in ids])

    def count(self, connection_id: str) -> int:
        return len(self.collection.get(where={"connection_id": connection_id}, include=[])["ids"])

    def health(self) -> bool:
        self.client.heartbeat()
        return True
