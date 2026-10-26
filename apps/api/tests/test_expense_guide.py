from collections.abc import Callable

from fastapi.testclient import TestClient

from app.services.expense_validation import EXPENSE_REQUIRED_FIELDS, expense_validation_errors


def test_guide_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/approvals/expense-guide").status_code == 401


def test_guide_fields_match_submission_contract_and_do_not_write(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    login(client, "seojin.yoon@jhworks.test")
    before = client.get("/api/v1/approvals").json()
    result = client.get("/api/v1/approvals/expense-guide")
    assert result.status_code == 200, result.text
    data = result.json()
    required = {f["field"] for f in data["fields"] if f["required"]}
    assert required == {"amount", *(f"details.{key}" for key in EXPENSE_REQUIRED_FIELDS)}
    assert required == set(expense_validation_errors({}, None))
    assert len({s["status"] for s in data["stages"]}) == 4
    assert len({q["id"] for q in data["questions"]}) == 4
    assert data["version"] == "expense-guide-v1"
    assert client.get("/api/v1/approvals").json() == before
    receipt = next(f for f in data["fields"] if f["field"] == "details.receiptReference")
    assert receipt["required"] is False and "진위" in receipt["description"]
