import hashlib
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.employee import Credential, Department, Employee
from app.models.enums import EmployeeRole, PolicyStatus, PolicyType
from app.models.policy import CompanyPolicy, PolicySection

DEMO_PASSWORD = "demo1234"


def _content_hash(sections: list[tuple[str, str, str]]) -> str:
    canonical = "\n".join("|".join(section) for section in sections)
    return hashlib.sha256(canonical.encode()).hexdigest()


def seed_database(db: Session) -> None:
    if db.scalar(select(Employee.id).limit(1)) is not None:
        return

    departments = [
        Department(id="dept_executive", name="Executive", is_active=True),
        Department(
            id="dept_sales",
            name="Sales",
            parent_department_id="dept_executive",
            is_active=True,
        ),
        Department(
            id="dept_engineering",
            name="Engineering",
            parent_department_id="dept_executive",
            is_active=True,
        ),
        Department(
            id="dept_corporate_ops",
            name="Corporate Operations",
            parent_department_id="dept_executive",
            is_active=True,
        ),
    ]
    db.add_all(departments)
    db.flush()

    employees = [
        Employee(
            id="emp_ceo_001",
            name="강유진",
            email="yujin.kang@jhworks.test",
            department_id="dept_executive",
            position="CEO",
            role=EmployeeRole.MANAGER,
            manager_id=None,
            hire_date=date(2021, 1, 4),
            leave_balance=18,
            is_active=True,
        ),
        Employee(
            id="emp_sales_mgr_001",
            name="최도윤",
            email="doyun.choi@jhworks.test",
            department_id="dept_sales",
            position="Sales Manager",
            role=EmployeeRole.MANAGER,
            manager_id="emp_ceo_001",
            hire_date=date(2022, 3, 14),
            leave_balance=14,
            is_active=True,
        ),
        Employee(
            id="emp_sales_001",
            name="윤서진",
            email="seojin.yoon@jhworks.test",
            department_id="dept_sales",
            position="Account Executive",
            role=EmployeeRole.EMPLOYEE,
            manager_id="emp_sales_mgr_001",
            hire_date=date(2024, 2, 5),
            leave_balance=9.5,
            is_active=True,
        ),
        Employee(
            id="emp_sales_002",
            name="김하린",
            email="harin.kim@jhworks.test",
            department_id="dept_sales",
            position="Account Executive",
            role=EmployeeRole.EMPLOYEE,
            manager_id="emp_sales_mgr_001",
            hire_date=date(2025, 1, 6),
            leave_balance=7,
            is_active=True,
        ),
        Employee(
            id="emp_eng_mgr_001",
            name="서지후",
            email="jihoo.seo@jhworks.test",
            department_id="dept_engineering",
            position="Engineering Manager",
            role=EmployeeRole.MANAGER,
            manager_id="emp_ceo_001",
            hire_date=date(2022, 7, 11),
            leave_balance=13,
            is_active=True,
        ),
        Employee(
            id="emp_eng_001",
            name="류민재",
            email="minjae.ryu@jhworks.test",
            department_id="dept_engineering",
            position="Software Engineer",
            role=EmployeeRole.EMPLOYEE,
            manager_id="emp_eng_mgr_001",
            hire_date=date(2024, 9, 2),
            leave_balance=10,
            is_active=True,
        ),
        Employee(
            id="emp_ops_001",
            name="한가람",
            email="garam.han@jhworks.test",
            department_id="dept_corporate_ops",
            position="Policy Operations Lead",
            role=EmployeeRole.POLICY_OWNER,
            manager_id="emp_ceo_001",
            hire_date=date(2023, 5, 8),
            leave_balance=12.5,
            is_active=True,
        ),
    ]
    db.add_all(employees)
    db.flush()

    manager_by_department = {
        "dept_executive": "emp_ceo_001",
        "dept_sales": "emp_sales_mgr_001",
        "dept_engineering": "emp_eng_mgr_001",
        "dept_corporate_ops": "emp_ops_001",
    }
    for department in departments:
        department.manager_employee_id = manager_by_department[department.id]

    demo_ids = {"emp_sales_001", "emp_sales_mgr_001", "emp_ops_001"}
    password = hash_password(DEMO_PASSWORD)
    db.add_all(
        [Credential(employee_id=employee_id, password_hash=password) for employee_id in demo_ids]
    )

    policy_data: list[tuple[str, PolicyType, str, list[tuple[str, str, str]]]] = [
        (
            "policy_travel",
            PolicyType.TRAVEL,
            "Domestic Business Travel Policy",
            [
                (
                    "TRAVEL-1",
                    "Accommodation",
                    "Domestic accommodation is reimbursed up to KRW 120,000 per night.",
                ),
                (
                    "TRAVEL-2",
                    "Transportation",
                    "Transportation is reimbursed at actual documented cost.",
                ),
                (
                    "TRAVEL-3",
                    "Prior approval",
                    "Trips with an estimated total cost of KRW 300,000 or more "
                    "require prior approval.",
                ),
                (
                    "TRAVEL-4",
                    "Client visits",
                    "A client visit request must state the client name and specific visit purpose.",
                ),
            ],
        ),
        (
            "policy_expense",
            PolicyType.EXPENSE,
            "Business Expense Policy",
            [
                (
                    "EXPENSE-1",
                    "Client meals",
                    "A client meeting meal is limited to KRW 50,000 per attendee.",
                ),
                (
                    "EXPENSE-2",
                    "Receipts",
                    "Expenses of KRW 100,000 or more require a receipt.",
                ),
                (
                    "EXPENSE-3",
                    "Prior approval",
                    "Expenses of KRW 300,000 or more require prior approval.",
                ),
            ],
        ),
        (
            "policy_leave",
            PolicyType.LEAVE,
            "Annual Leave Policy",
            [
                (
                    "LEAVE-1",
                    "Balance",
                    "Annual leave may be requested only within the employee's remaining balance.",
                ),
                (
                    "LEAVE-2",
                    "Advance notice",
                    "Three or more consecutive leave days require five business days "
                    "of advance notice.",
                ),
                (
                    "LEAVE-3",
                    "Half day",
                    "A half-day request deducts 0.5 day from the leave balance.",
                ),
            ],
        ),
    ]

    now = datetime.now(UTC)
    for policy_id, policy_type, title, sections in policy_data:
        policy = CompanyPolicy(
            record_id=f"{policy_id}_v1.0",
            policy_id=policy_id,
            type=policy_type,
            title=title,
            version="1.0",
            status=PolicyStatus.ACTIVE,
            effective_from=date(2026, 1, 1),
            content_hash=_content_hash(sections),
            published_at=now,
        )
        policy.sections = [
            PolicySection(section_id=section_id, title=section_title, content=content, order=index)
            for index, (section_id, section_title, content) in enumerate(sections, start=1)
        ]
        db.add(policy)

    db.commit()


def main() -> None:
    with SessionLocal() as db:
        seed_database(db)


if __name__ == "__main__":
    main()
