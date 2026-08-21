from app.models.approval import Approval, ApprovalLine
from app.models.employee import Department, Employee
from app.models.policy import CompanyPolicy, PolicySection
from app.schemas.approval import ApprovalLineRead, ApprovalRead
from app.schemas.employee import CurrentEmployeeRead, DepartmentRead, EmployeeSummary
from app.schemas.policy import PolicyRead, PolicySectionRead


def department_read(department: Department) -> DepartmentRead:
    return DepartmentRead.model_validate(department)


def employee_summary(employee: Employee) -> EmployeeSummary:
    return EmployeeSummary.model_validate(employee)


def current_employee_read(employee: Employee) -> CurrentEmployeeRead:
    return CurrentEmployeeRead(
        id=employee.id,
        name=employee.name,
        email=employee.email,
        department_id=employee.department_id,
        position=employee.position,
        role=employee.role,
        hire_date=employee.hire_date,
        leave_balance=employee.leave_balance,
        manager=employee_summary(employee.manager) if employee.manager else None,
        department=department_read(employee.department),
    )


def approval_line_read(line: ApprovalLine) -> ApprovalLineRead:
    return ApprovalLineRead(
        id=line.id,
        step=line.step,
        round=line.round,
        approver=employee_summary(line.approver),
        status=line.status,
        comment=line.comment,
        acted_at=line.acted_at,
    )


def approval_read(approval: Approval) -> ApprovalRead:
    return ApprovalRead(
        id=approval.id,
        type=approval.type,
        title=approval.title,
        content=approval.content,
        author=employee_summary(approval.author),
        status=approval.status,
        amount=approval.amount,
        details=approval.details,
        attachment_metadata=approval.attachment_metadata,
        version=approval.version,
        submitted_at=approval.submitted_at,
        decided_at=approval.decided_at,
        created_at=approval.created_at,
        updated_at=approval.updated_at,
        lines=[approval_line_read(line) for line in approval.lines],
    )


def policy_section_read(section: PolicySection) -> PolicySectionRead:
    return PolicySectionRead.model_validate(section)


def policy_read(policy: CompanyPolicy) -> PolicyRead:
    return PolicyRead(
        id=policy.policy_id,
        type=policy.type,
        title=policy.title,
        version=policy.version,
        effective_from=policy.effective_from,
        content_hash=policy.content_hash,
        published_at=policy.published_at,
        sections=[policy_section_read(section) for section in policy.sections],
    )
