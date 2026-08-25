from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import EmployeeRole

if TYPE_CHECKING:
    from app.models.approval import Approval, ApprovalLine


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    parent_department_id: Mapped[str | None] = mapped_column(
        ForeignKey("departments.id"), nullable=True
    )
    manager_employee_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), nullable=False)
    position: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[EmployeeRole] = mapped_column(
        Enum(EmployeeRole, native_enum=False, length=32), nullable=False
    )
    manager_id: Mapped[str | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    leave_balance: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    department: Mapped[Department] = relationship(foreign_keys=[department_id])
    manager: Mapped["Employee | None"] = relationship(remote_side=[id], foreign_keys=[manager_id])
    authored_approvals: Mapped[list["Approval"]] = relationship(
        back_populates="author", foreign_keys="Approval.author_id"
    )
    assigned_lines: Mapped[list["ApprovalLine"]] = relationship(back_populates="approver")
    credential: Mapped["Credential | None"] = relationship(
        back_populates="employee", uselist=False, cascade="all, delete-orphan"
    )


class Credential(Base):
    __tablename__ = "credentials"

    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    employee: Mapped[Employee] = relationship(back_populates="credential")
