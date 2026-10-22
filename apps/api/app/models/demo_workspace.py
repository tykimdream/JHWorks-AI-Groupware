from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DemoWorkspace(Base):
    __tablename__ = "demo_workspaces"
    __table_args__ = (
        CheckConstraint("request_limit BETWEEN 1 AND 500", name="ck_demo_workspace_requests_limit"),
        CheckConstraint(
            "requests_used >= 0 AND requests_used <= request_limit",
            name="ck_demo_workspace_requests_usage",
        ),
        CheckConstraint("expires_at_epoch > 0", name="ck_demo_workspace_expiry"),
        CheckConstraint("write_limit BETWEEN 1 AND 100", name="ck_demo_workspace_limit"),
        CheckConstraint(
            "writes_used >= 0 AND writes_used <= write_limit", name="ck_demo_workspace_usage"
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), unique=True)
    expires_at_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    write_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    writes_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default=text("100")
    )
    requests_used: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
