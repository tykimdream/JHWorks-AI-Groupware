from sqlalchemy import BigInteger, CheckConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DemoStartBudget(Base):
    __tablename__ = "demo_start_budget"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_demo_start_singleton"),
        CheckConstraint("day_number >= 0", name="ck_demo_start_day"),
        CheckConstraint("starts_used >= 1", name="ck_demo_start_usage"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    day_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    starts_used: Mapped[int] = mapped_column(Integer, nullable=False)
