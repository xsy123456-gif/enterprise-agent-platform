from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ApprovalRequest:
    agent_id: str
    version: str
    requester: str
    approval_channel: str = "manual"
    status: str = ApprovalStatus.PENDING.value
    reviewer: str | None = None
    comment: str | None = None
    approval_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=utc_now)
