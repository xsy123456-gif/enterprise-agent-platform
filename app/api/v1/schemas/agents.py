"""Agent + message public schemas (Phase 18.12)."""

from app.api.v1.schemas.common import PublicModel, ResourceLink


class AgentSummary(PublicModel):
    agent_id: str
    name: str
    description: str = ""
    version: str = ""
    domain: str = ""
    status: str = "ACTIVE"


class AgentListResponse(PublicModel):
    items: list[AgentSummary]
    next_cursor: str | None = None


class MessageRequest(PublicModel):
    message: str
    session_id: str | None = None
    locale: str | None = None


class ExecutionRef(PublicModel):
    execution_id: str
    status: str
    agent_id: str
    agent_version: str


class ResponseBody(PublicModel):
    content: str
    citations: list[str] = []


class MessageResponse(PublicModel):
    request_id: str
    session_id: str | None = None
    execution: ExecutionRef | None = None
    response: ResponseBody
    pending: str | None = None
    links: dict = {}


__all__ = [
    "AgentSummary",
    "AgentListResponse",
    "MessageRequest",
    "ExecutionRef",
    "ResponseBody",
    "MessageResponse",
    "ResourceLink",
]
