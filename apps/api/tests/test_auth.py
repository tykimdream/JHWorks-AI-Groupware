from fastapi.testclient import TestClient


def test_login_returns_current_employee(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "seojin.yoon@jhworks.test", "password": "demo1234"},
    )

    assert response.status_code == 200
    employee = response.json()["employee"]
    assert employee["id"] == "emp_sales_001"
    assert employee["department"]["name"] == "Sales"
    assert employee["manager"]["id"] == "emp_sales_mgr_001"
    assert "jhworks_session" in response.cookies


def test_protected_endpoint_requires_session(client: TestClient) -> None:
    response = client.get("/api/v1/employees/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_wrong_password_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "seojin.yoon@jhworks.test", "password": "wrong-pass"},
    )

    assert response.status_code == 401


def test_unrelated_reserved_email_domain_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@other-company.test", "password": "demo1234"},
    )

    assert response.status_code == 422
