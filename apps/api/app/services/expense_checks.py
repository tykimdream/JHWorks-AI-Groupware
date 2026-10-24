from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.errors import DomainValidationError
from app.models.approval import Approval
from app.models.employee import Employee
from app.models.enums import ApprovalStatus, ApprovalType
from app.schemas.expense_checks import ExpenseChecks, ExpenseInsights, ExpenseMatch
from app.services.approval import get_approval, visible_approval_query
from app.services.expense_validation import expense_validation_errors

HOME_DOCUMENT_LIMIT = 10
MATCH_LIMIT = 3


def _check(db: Session, actor: Employee, approval: Approval) -> ExpenseChecks:
    missing = list(expense_validation_errors(approval.details, approval.amount))
    matches: list[Approval] = []
    merchant = approval.details.get("merchant")
    # Exact payment facts are evidence of a possible duplicate, never proof of one.
    if (
        isinstance(merchant, str)
        and merchant.strip()
        and "details.expenseDate" not in missing
        and approval.amount is not None
        and approval.amount > 0
    ):
        statement = (
            visible_approval_query(actor)
            .where(
                Approval.id != approval.id,
                Approval.author_id == approval.author_id,
                Approval.type == ApprovalType.EXPENSE,
                Approval.status != ApprovalStatus.REJECTED,
                Approval.amount == approval.amount,
                Approval.details["expenseDate"].as_string() == approval.details.get("expenseDate"),
                func.trim(Approval.details["merchant"].as_string()) == merchant.strip(),
            )
            .order_by(Approval.updated_at.desc(), Approval.id)
            .limit(MATCH_LIMIT + 1)
        )
        matches = list(db.scalars(statement).unique())
    return ExpenseChecks(
        approval_id=approval.id,
        approval_title=approval.title,
        version=approval.version,
        missing_fields=missing,
        duplicate_matches=[
            ExpenseMatch(id=item.id, title=item.title, status=item.status)
            for item in matches[:MATCH_LIMIT]
        ],
        more_matches=len(matches) > MATCH_LIMIT,
        checked_at=datetime.now(UTC),
    )


def check_expense(db: Session, actor: Employee, approval_id: str) -> ExpenseChecks:
    approval = get_approval(db, actor, approval_id)
    if approval.type != ApprovalType.EXPENSE:
        raise DomainValidationError("NOT_AN_EXPENSE", "Expense checks require an expense approval")
    return _check(db, actor, approval)


def expense_insights(db: Session, actor: Employee) -> ExpenseInsights:
    statement = (
        visible_approval_query(actor)
        .where(
            Approval.author_id == actor.id,
            Approval.type == ApprovalType.EXPENSE,
            Approval.status.in_([ApprovalStatus.DRAFT, ApprovalStatus.PENDING]),
        )
        .order_by(Approval.updated_at.desc(), Approval.id)
        .limit(HOME_DOCUMENT_LIMIT + 1)
    )
    documents = list(db.scalars(statement).unique())
    checked = [_check(db, actor, document) for document in documents[:HOME_DOCUMENT_LIMIT]]
    return ExpenseInsights(
        items=[item for item in checked if item.missing_fields or item.duplicate_matches],
        checked_count=len(checked),
        has_more_documents=len(documents) > HOME_DOCUMENT_LIMIT,
        checked_at=datetime.now(UTC),
    )
