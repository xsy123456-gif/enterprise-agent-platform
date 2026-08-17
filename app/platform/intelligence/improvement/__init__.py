"""Improvement subpackage (Phase 17.3)."""

from app.platform.intelligence.improvement.approval import ImprovementApproval
from app.platform.intelligence.improvement.lifecycle import (
    AgentImprovementRequest,
    ImprovementLifecycle,
)

__all__ = ["AgentImprovementRequest", "ImprovementLifecycle",
           "ImprovementApproval"]
