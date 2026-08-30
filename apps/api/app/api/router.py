from fastapi import APIRouter

from app.api.routes import (
    approval_drafts,
    approvals,
    attendance,
    auth,
    employees,
    health,
    leave_agent,
    leave_assistant,
    leave_draft_tool,
    policies,
    work_assistant,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(employees.router)
api_router.include_router(approvals.router)
api_router.include_router(attendance.router)
api_router.include_router(leave_assistant.router)
api_router.include_router(leave_agent.router)
api_router.include_router(leave_draft_tool.router)
api_router.include_router(approval_drafts.router)
api_router.include_router(policies.router)
api_router.include_router(work_assistant.router)
