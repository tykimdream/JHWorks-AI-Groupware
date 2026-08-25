from datetime import UTC, date, datetime
from typing import Any

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import PolicyStatus, PolicyType


def utc_now() -> datetime:
    return datetime.now(UTC)


class CompanyPolicy(Base):
    __tablename__ = "company_policies"
    __table_args__ = (UniqueConstraint("policy_id", "version", name="uq_policy_version"),)

    record_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    type: Mapped[PolicyType] = mapped_column(
        Enum(PolicyType, native_enum=False, length=32), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[PolicyStatus] = mapped_column(
        Enum(PolicyStatus, native_enum=False, length=32), nullable=False, index=True
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sections: Mapped[list["PolicySection"]] = relationship(
        back_populates="policy", cascade="all, delete-orphan", order_by="PolicySection.order"
    )


class PolicySection(Base):
    __tablename__ = "policy_sections"
    __table_args__ = (
        UniqueConstraint("policy_record_id", "section_id", name="uq_policy_section_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_record_id: Mapped[str] = mapped_column(
        ForeignKey("company_policies.record_id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        VECTOR(1536).with_variant(JSON(), "sqlite"), nullable=True
    )
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedded_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rule_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    policy: Mapped[CompanyPolicy] = relationship(back_populates="sections")
