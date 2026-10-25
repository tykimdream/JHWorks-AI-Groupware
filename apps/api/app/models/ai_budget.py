"""Admission ledger only: no prompts, credentials, or provider response bodies."""

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AIBudgetCounter(Base):
    __tablename__ = "ai_budget_counters"
    __table_args__ = (
        CheckConstraint("reserved_micro_usd >= 0", name="ck_ai_counter_reserved"),
        CheckConstraint("spent_micro_usd >= 0", name="ck_ai_counter_spent"),
        CheckConstraint("admissions >= 0", name="ck_ai_counter_admissions"),
        CheckConstraint("active_requests >= 0", name="ck_ai_counter_active"),
        CheckConstraint("last_observed_epoch >= 0", name="ck_ai_counter_clock"),
    )

    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    reserved_micro_usd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    spent_micro_usd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    admissions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_observed_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    is_frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AIBudgetReservation(Base):
    __tablename__ = "ai_budget_reservations"
    __table_args__ = (
        CheckConstraint("maximum_micro_usd > 0", name="ck_ai_reservation_maximum"),
        CheckConstraint("created_at_epoch > 0", name="ck_ai_reservation_created"),
        CheckConstraint(
            "status IN ('RESERVED', 'SETTLED', 'UNCERTAIN', 'OVERRUN')",
            name="ck_ai_reservation_status",
        ),
        CheckConstraint(
            "(status = 'RESERVED' AND charged_micro_usd IS NULL) OR "
            "(status <> 'RESERVED' AND charged_micro_usd IS NOT NULL AND charged_micro_usd >= 0)",
            name="ck_ai_reservation_charge",
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    day_key: Mapped[str] = mapped_column(ForeignKey("ai_budget_counters.key"), nullable=False)
    month_key: Mapped[str] = mapped_column(ForeignKey("ai_budget_counters.key"), nullable=False)
    scope_key: Mapped[str] = mapped_column(ForeignKey("ai_budget_counters.key"), nullable=False)
    maximum_micro_usd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    charged_micro_usd: Mapped[int | None] = mapped_column(BigInteger)
    created_at_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="RESERVED", server_default=text("'RESERVED'")
    )
