"""Conversation history (Phase 12.4)."""

from dataclasses import dataclass, field

from app.commerce.domain.base import utc_now


@dataclass(frozen=True)
class ConversationTurn:
    role: str
    content: str
    at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content, "at": self.at}


class ConversationHistory:
    """Ordered turn list.  Manages history only — no data query / permission /
    business analysis."""

    def __init__(self):
        self._turns = []

    def append(self, role, content) -> ConversationTurn:
        turn = ConversationTurn(role=role, content=content)
        self._turns.append(turn)
        return turn

    def turns(self) -> tuple[ConversationTurn, ...]:
        return tuple(self._turns)

    def recent(self, n) -> tuple[ConversationTurn, ...]:
        return tuple(self._turns[-n:])

    def to_dict(self) -> dict:
        return {"turns": [t.to_dict() for t in self._turns]}

    def __len__(self):
        return len(self._turns)


__all__ = ["ConversationTurn", "ConversationHistory"]
