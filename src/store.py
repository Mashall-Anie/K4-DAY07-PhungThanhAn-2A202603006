from __future__ import annotations

from typing import Any, Callable

from .chunking import _dot
from .embeddings import _mock_embed
from .models import Document


class EmbeddingStore:
    """
    A vector store for text chunks.

    Tries to use ChromaDB if available; falls back to an in-memory store.
    The embedding_fn parameter allows injection of mock embeddings for tests.
    """

    def __init__(self, collection_name="documents", embedding_fn=None):
        self._embedding_fn = embedding_fn or _mock_embed
        self._store: list[dict] = []

    def add_documents(self, docs):
        for doc in docs:
            self._store.append({
                "id": doc.id,
                "content": doc.content, 
                "metadata": {"doc_id": doc.id, **doc.metadata},                
                "embedding": self._embedding_fn(doc.content),
            })

    def _rank(self, records, query, top_k):
        q = self._embedding_fn(query)
        scored = [{"content": r["content"], "metadata": r["metadata"],
                   "score": sum(a * b for a, b in zip(q, r["embedding"]))}   # dot product
                  for r in records]
        return sorted(scored, key=lambda x: x["score"], reverse=True)[:top_k]

    def search(self, query, top_k=3):
        return self._rank(self._store, query, top_k)

    def get_collection_size(self):
        return len(self._store)

    def search_with_filter(self, query, top_k=3, metadata_filter=None):
        records = self._store
        if metadata_filter:
            records = [r for r in records
                       if all(r["metadata"].get(k) == v for k, v in metadata_filter.items())]
        return self._rank(records, query, top_k)     # lọc TRƯỚC, tìm SAU

    def delete_document(self, doc_id):
        before = len(self._store)
        self._store = [r for r in self._store if r["metadata"].get("doc_id") != doc_id]
        return len(self._store) < before