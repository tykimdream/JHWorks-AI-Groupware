from collections.abc import Mapping
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.models.enums import ExpenseCategory

EXPENSE_REQUIRED_FIELDS = ("expenseDate", "merchant", "category", "purpose")


def expense_validation_errors(
    details: Mapping[str, object],
    amount: int | None,
) -> dict[str, str]:
    """Drafts may be incomplete; prepared previews and submissions must be grounded."""
    errors: dict[str, str] = {}
    for field in EXPENSE_REQUIRED_FIELDS:
        value = details.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors[f"details.{field}"] = "This field is required for expense settlement"
    raw_date = details.get("expenseDate")
    try:
        spent = date.fromisoformat(raw_date) if isinstance(raw_date, str) else None
    except ValueError:
        spent = None
    if spent is None:
        errors["details.expenseDate"] = "A valid payment date is required"
    elif spent > datetime.now(ZoneInfo("Asia/Seoul")).date():
        errors["details.expenseDate"] = "Settlement cannot use a future payment date"
    category = details.get("category")
    if category is not None and category not in {item.value for item in ExpenseCategory}:
        errors["details.category"] = "Unknown expense category"
    if amount is None or amount <= 0:
        errors["amount"] = "A positive actual expense amount is required"
    return errors
