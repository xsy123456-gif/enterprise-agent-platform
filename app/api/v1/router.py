"""V1 product router (Phase 18.12)."""

from fastapi import APIRouter

from app.api.v1.endpoints import agents, approvals, executions, workflows

router = APIRouter()
router.include_router(agents.router)
router.include_router(executions.router)
router.include_router(approvals.router)
router.include_router(workflows.router)


__all__ = ["router"]
