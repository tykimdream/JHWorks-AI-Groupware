"""Disposable browser performance fixture; never mounted by the deployed app."""
from datetime import UTC, datetime, timedelta

from app.models import Approval, ApprovalLine
from app.models.enums import ApprovalLineStatus, ApprovalStatus, ApprovalType
from tests import e2e_server

app = e2e_server.app  # type: ignore[attr-defined]
factory = e2e_server.factory

with factory() as db:
    clock = datetime(2026, 1, 1, tzinfo=UTC)
    for index in range(1000):
        document_id = f"perf-document-{index:05d}"
        db.add(Approval(
            id=document_id, type=ApprovalType.EXPENSE, title=f"Synthetic expense {index:05d}",
            content="Synthetic expense body. " * 40, author_id="emp_sales_001",
            status=ApprovalStatus.PENDING, amount=170000,
            details={"kind": "EXPENSE", "expenseDate": "2026-01-01", "merchant": "Synthetic",
                     "category": "OTHER", "purpose": "Synthetic benchmark"},
            attachment_metadata=[{"name": "synthetic.pdf", "contentType": "application/pdf"}],
            version=4, created_at=clock, updated_at=clock + timedelta(seconds=index // 4),
            submitted_at=clock,
        ))
        for round_number in (1, 2):
            db.add(ApprovalLine(
                id=f"perf-line-{index:05d}-{round_number}", approval_id=document_id,
                step=1, round=round_number, approver_id="emp_sales_mgr_001",
                status=ApprovalLineStatus.REJECTED if round_number == 1
                else ApprovalLineStatus.PENDING,
            ))
    db.commit()
