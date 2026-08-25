from fastapi import APIRouter

from app.api.routes import approvals, auth, employees, health, policies

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(employees.router)
api_router.include_router(approvals.router)
api_router.include_router(policies.router)
