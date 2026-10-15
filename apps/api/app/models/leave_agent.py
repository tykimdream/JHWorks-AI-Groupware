from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import LeaveAgentStatus


def utc_now() -> datetime:
    return datetime.now(UTC)


class LeaveAgentRun(Base):
    __tablename__ = "leave_agent_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    approval_id: Mapped[str | None] = mapped_column(
        ForeignKey("approvals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[LeaveAgentStatus] = mapped_column(
        Enum(LeaveAgentStatus, native_enum=False, length=40), nullable=False, index=True
    )
    request: Mapped[str] = mapped_column(Text, nullable=False)
    answers: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    consultation_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    draft_preview: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    submit_preview: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    submit_confirmation_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )
    submit_confirmation_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    trace: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
