from fastapi import APIRouter
from sqlalchemy import select

from app.api.dependencies import CurrentEmployee, DbSession
from app.models.employee import Department
from app.schemas.employee import CurrentEmployeeRead, DepartmentRead
from app.services.mappers import current_employee_read, department_read

router = APIRouter(tags=["조직"])


@router.get("/employees/me", response_model=CurrentEmployeeRead, summary="내 직원 정보 조회")
def me(current_employee: CurrentEmployee) -> CurrentEmployeeRead:
    """로그인한 직원의 부서·역할·직속 관리자 정보를 조회합니다."""
    return current_employee_read(current_employee)


@router.get("/departments", response_model=list[DepartmentRead], summary="부서 목록 조회")
def departments(db: DbSession, current_employee: CurrentEmployee) -> list[DepartmentRead]:
    """
    조회 가능한 활성 부서를 반환합니다. 공개 체험에서는 현재 체험
    조직의 부서로 제한합니다.
    """
    query = select(Department).where(Department.is_active.is_(True))
    if current_employee.demo_workspace_id is not None:
        query = query.where(Department.id == current_employee.department_id)
    items = db.scalars(query.order_by(Department.name))
    return [department_read(item) for item in items]
