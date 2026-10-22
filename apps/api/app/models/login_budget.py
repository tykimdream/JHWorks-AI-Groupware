from sqlalchemy import BigInteger, CheckConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LoginBudget(Base):
    """One shared counter; never stores an email, IP address or credential."""

    __tablename__ = "login_budget"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_login_budget_singleton"),
        CheckConstraint("window >= 0", name="ck_login_budget_window"),
        CheckConstraint("attempts >= 1", name="ck_login_budget_attempts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    window: Mapped[int] = mapped_column(BigInteger, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
