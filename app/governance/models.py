from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid


def utc_now():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentLifecycle:
    agent_id: str
    version: str
    owner: str = ""
    status: str = "draft"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    approved_by: Optional[str] = None
    approval_time: Optional[str] = None


@dataclass
class ApprovalRequest:
    agent_id: str
    version: str
    requester: str
    approval_channel: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "pending"
    reviewer: Optional[str] = None
    comment: Optional[str] = None
