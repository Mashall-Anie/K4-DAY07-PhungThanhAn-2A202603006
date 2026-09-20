from __future__ import annotations

from typing import Callable

from .store import EmbeddingStore


class KnowledgeBaseAgent:
    NOT_FOUND = "Không tìm thấy thông tin liên quan trong cơ sở tri thức."

    def __init__(self, store: EmbeddingStore, llm_fn: Callable[[str], str]) -> None:
        self.store = store
        self.llm_fn = llm_fn

    def answer(self, question: str, top_k: int = 3, metadata_filter: dict | None = None) -> str:
        if metadata_filter:
            results = self.store.search_with_filter(question, top_k=top_k, metadata_filter=metadata_filter)
        else:
            results = self.store.search(question, top_k=top_k)

        if not results:
            return self.NOT_FOUND

        context = "\n\n".join(
            f"[{i}] (nguồn: {r['metadata'].get('doc_id', 'không rõ')}) {r['content']}"
            for i, r in enumerate(results, start=1)
        )
        prompt = (
            "Chỉ trả lời dựa trên ngữ cảnh dưới đây. "
            "Nếu ngữ cảnh không có thông tin, hãy nói rõ là không biết. "
            "Khi trả lời, ghi số thứ tự nguồn đã dùng, ví dụ [1].\n\n"
            f"Ngữ cảnh:\n{context}\n\nCâu hỏi: {question}\nTrả lời:"
        )
        return self.llm_fn(prompt)