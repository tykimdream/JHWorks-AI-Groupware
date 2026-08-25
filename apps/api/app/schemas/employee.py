from datetime import date
from decimal import Decimal

from app.core.schema import ApiSchema
from app.models.enums import EmployeeRole


class DepartmentRead(ApiSchema):
    id: str
    name: str
    parent_department_id: str | None
    manager_employee_id: str | None
    is_active: bool


class EmployeeSummary(ApiSchema):
    id: str
    name: str
    email: str
    department_id: str
    position: str
    role: EmployeeRole


class CurrentEmployeeRead(EmployeeSummary):
    hire_date: date
    leave_balance: Decimal
    manager: EmployeeSummary | None
    department: DepartmentRead
