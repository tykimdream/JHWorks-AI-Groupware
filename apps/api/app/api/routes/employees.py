from fastapi import APIRouter
from sqlalchemy import select

from app.api.dependencies import CurrentEmployee, DbSession
from app.models.employee import Department
from app.schemas.employee import CurrentEmployeeRead, DepartmentRead
from app.services.mappers import current_employee_read, department_read

router = APIRouter(tags=["organization"])


@router.get("/employees/me", response_model=CurrentEmployeeRead)
def me(current_employee: CurrentEmployee) -> CurrentEmployeeRead:
    return current_employee_read(current_employee)


@router.get("/departments", response_model=list[DepartmentRead])
def departments(db: DbSession, _: CurrentEmployee) -> list[DepartmentRead]:
    items = db.scalars(
        select(Department).where(Department.is_active.is_(True)).order_by(Department.name)
    )
    return [department_read(item) for item in items]
