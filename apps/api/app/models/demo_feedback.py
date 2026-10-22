from sqlalchemy import BigInteger, CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DemoFeedbackGate(Base):
    __tablename__ = "demo_feedback_gate"
    __table_args__ = (CheckConstraint("id = 1", name="ck_demo_feedback_gate_singleton"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)


class DemoFeedback(Base):
    __tablename__ = "demo_feedback"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    screen: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
