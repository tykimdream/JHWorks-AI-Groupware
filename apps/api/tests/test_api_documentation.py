import json
import os
import subprocess
import sys

from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_schema_describes_cookie_auth_on_protected_routes_only(client: TestClient) -> None:
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    scheme = schema["components"]["securitySchemes"]["SessionCookie"]
    assert scheme["in"] == "cookie"
    assert scheme["name"] == get_settings().session_cookie_name
    for path, method in [
        ("/api/v1/employees/me", "get"),
        ("/api/v1/approvals", "post"),
        ("/api/v1/demo/feedback", "post"),
    ]:
        assert {"SessionCookie": []} in schema["paths"][path][method]["security"]
    assert not schema["paths"]["/api/v1/demo/start"]["post"].get("security")
    assert not schema["paths"]["/api/v1/health/live"]["get"].get("security")
    # Documenting the cookie must preserve the application's 401 error contract.
    denied = client.get("/api/v1/employees/me")
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_swagger_paths_and_expense_contract_are_browsable_without_login(client: TestClient) -> None:
    response = client.get("/api/v1/docs")
    assert response.status_code == 200
    assert "/api/v1/openapi.json" in response.text
    assert "no-store" in response.headers["cache-control"]
    assert client.get("/docs", follow_redirects=False).headers["location"] == "/api/v1/docs"
    schema = client.get("/api/v1/openapi.json").json()
    tags = {item["name"]: item["description"] for item in schema["tags"]}
    used = {
        tag
        for path in schema["paths"].values()
        for op in path.values()
        for tag in op.get("tags", [])
    }
    assert used <= tags.keys()
    assert all(tags[tag] for tag in used)
    body_schema = schema["paths"]["/api/v1/approvals"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]["$ref"].rsplit("/", 1)[1]
    example = schema["components"]["schemas"][body_schema]["examples"][0]
    assert example["type"] == "EXPENSE" and example["amount"] == 170000
    assert example["details"]["kind"] == "EXPENSE"
    assert "description" in schema["paths"]["/api/v1/approvals/{approval_id}/submit"]["post"]


def test_public_swagger_disables_execution_with_real_public_configuration() -> None:
    # Fresh process: settings and FastAPI docs configuration are fixed at import time.
    program = """
import json
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    response = client.get('/api/v1/docs')
    print(json.dumps({'status': response.status_code, 'html': response.text}))
"""
    result = subprocess.run(
        [sys.executable, "-c", program],
        env={**os.environ, "JHWORKS_PUBLIC_DEMO_ENABLED": "true", "JHWORKS_AI_ENABLED": "false"},
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    output = json.loads(result.stdout)
    assert output["status"] == 200
    assert '"supportedSubmitMethods": []' in output["html"]
