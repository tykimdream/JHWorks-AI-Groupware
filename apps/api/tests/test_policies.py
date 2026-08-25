from collections.abc import Callable

from fastapi.testclient import TestClient


def test_active_policies_have_stable_sections(
    client: TestClient,
    login: Callable[[TestClient, str], None],
) -> None:
    login(client, "garam.han@jhworks.test")
    response = client.get("/api/v1/policies")

    assert response.status_code == 200
    policies = response.json()
    assert {policy["id"] for policy in policies} == {
        "policy_travel",
        "policy_expense",
        "policy_leave",
    }
    assert all(policy["version"] == "1.0" for policy in policies)
    assert all(policy["sections"] for policy in policies)
