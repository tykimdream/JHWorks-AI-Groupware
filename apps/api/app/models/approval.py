from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ApprovalLineStatus, ApprovalStatus, ApprovalType


def utc_now() -> datetime:
    return datetime.now(UTC)


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[ApprovalType] = mapped_column(
        Enum(ApprovalType, native_enum=False, length=32), nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    author_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, native_enum=False, length=32),
        nullable=False,
        default=ApprovalStatus.DRAFT,
        index=True,
    )
    amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    attachment_metadata: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    author = relationship("Employee", back_populates="authored_approvals", foreign_keys=[author_id])
    lines: Mapped[list["ApprovalLine"]] = relationship(
        back_populates="approval",
        cascade="all, delete-orphan",
        order_by="ApprovalLine.round",
    )


class ApprovalLine(Base):
    __tablename__ = "approval_lines"
    __table_args__ = (
        UniqueConstraint("approval_id", "round", "step", name="uq_approval_line_round_step"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    approval_id: Mapped[str] = mapped_column(
        ForeignKey("approvals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    status: Mapped[ApprovalLineStatus] = mapped_column(
        Enum(ApprovalLineStatus, native_enum=False, length=32), nullable=False
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    approval: Mapped[Approval] = relationship(back_populates="lines")
    approver = relationship("Employee", back_populates="assigned_lines")
