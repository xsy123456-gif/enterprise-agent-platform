"""LLM-based reranker (optional, internally-configurable).

Uses an injected LLM to reorder retrieval hits by relevance.  This is a
platform-internal strategy; Agents never select the reranker.
"""

import json

from app.knowledge.ports.reranker import KnowledgeRerankerPort

_RERANK_PROMPT = """你是检索重排序器。根据用户问题，对候选片段按相关性从高到低排序。

只输出 JSON 数组，元素为候选片段序号（0 起始），按相关性降序：
[2, 0, 1]

用户问题：
{query}

候选片段：
{candidates}
"""


class LLMReranker(KnowledgeRerankerPort):
    def __init__(self, llm, top_k=None):
        if llm is None:
            raise ValueError("LLMReranker requires an LLM")
        self.llm = llm
        self.top_k = top_k

    async def rerank(self, query: str, hits):
        if not hits:
            return hits
        if len(hits) == 1:
            return hits

        candidates = "\n".join(
            f"[{index}] {hit.content[:200]}" for index, hit in enumerate(hits)
        )
        messages = [
            {
                "role": "user",
                "content": _RERANK_PROMPT.format(query=query, candidates=candidates),
            }
        ]
        try:
            response = self.llm.chat(messages)
            order = self._parse_order(response, len(hits))
        except Exception:
            return hits
        reordered = [hits[index] for index in order if 0 <= index < len(hits)]
        # Preserve any hits the model dropped (safety).
        reordered += [hit for hit in hits if hit not in reordered]
        return reordered[: self.top_k] if self.top_k else reordered

    @staticmethod
    def _parse_order(response, count):
        text = (response or "").strip()
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            text = text[start:end + 1]
        try:
            order = json.loads(text)
        except json.JSONDecodeError:
            return list(range(count))
        return [int(index) for index in order]
