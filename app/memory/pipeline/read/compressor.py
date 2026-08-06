import json


class MemoryCompressor:
    def __init__(self, llm=None):
        self.llm = llm

    def compress(self, candidates, query):
        if not candidates:
            return ""
        facts = [{"key": item.memory_key, "content": item.content} for item, _ in candidates]
        if self.llm is None:
            return "\n".join(
                f"- {fact['key']}: {json.dumps(fact['content'], ensure_ascii=False)}"
                for fact in facts
            )
        return self.llm.chat([
            {"role": "system", "content": "Compress supplied memory facts. Do not add facts."},
            {"role": "user", "content": json.dumps({"query": query, "facts": facts}, ensure_ascii=False)},
        ])
