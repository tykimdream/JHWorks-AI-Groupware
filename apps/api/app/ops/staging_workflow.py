"""One-time HTTP workflow validation of the private, freshly initialized staging fixture."""

import argparse
import getpass
import json
import sys
import warnings
from collections.abc import Mapping
from contextlib import ExitStack
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

import httpx

from app.ops.staging_backup import run
from app.ops.staging_fixture import IDS, verify_private_service

ORIGIN = "https://jhworks-staging-968398406137.asia-northeast3.run.app"
ACTORS = ("author", "approver", "unrelated")


class HttpClient(Protocol):
    def request(
        self, method: str, url: str, *, json: Any = None,
        params: dict[str, str] | None = None, headers: dict[str, str] | None = None,
    ) -> Any: ...


class Workflow:
    def __init__(self, clients: Mapping[str, HttpClient]) -> None:
        self.clients = clients
        self.stage = "initialization"
        self.passed: list[str] = []

    def run_remote(self, password: str, commit: str) -> None:
        self.stage = "ingress_authentication"
        token = run(["gcloud", "auth", "print-identity-token"],
                    capture_output=True, text=True).stdout.strip()
        if not token:
            raise ValueError("Google ID token missing")
        self.stage = "service_recheck"
        verify_private_service(commit)
        with ExitStack() as stack:
            self.clients = {actor: stack.enter_context(httpx.Client(
                base_url=ORIGIN, timeout=60, follow_redirects=False, trust_env=False,
                headers={"Origin": ORIGIN, "X-Serverless-Authorization": "Bearer " + token},
            )) for actor in ACTORS}
            self.execute(password, datetime.now(UTC).year)

    def require(self, name: str, condition: bool) -> None:
        self.stage = name
        if not condition:
            raise ValueError("workflow check failed")
        self.passed.append(name)

    def request(
        self, name: str, actor: str, method: str, path: str, status: int = 200,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.stage = name
        response = self.clients[actor].request(method, "/api/v1" + path, **kwargs)
        self.require(name, response.status_code == status)
        if path == "/auth/login" and status == 200:
            cookies = list(response.cookies.jar)
            self.require(name + "_secure_cookie", len(cookies) == 1 and cookies[0].secure
                         and cookies[0].has_nonstandard_attr("HttpOnly")
                         and cookies[0].get_nonstandard_attr("SameSite") == "lax")
        value = response.json()
        if not isinstance(value, dict):
            raise ValueError("expected JSON object")
        return value

    def overview(self, name: str, day: str, used: str, pending: str, event: str | None) -> None:
        value = self.request(name, "author", "GET", "/attendance/overview",
                             params={"startDate": day, "endDate": day})
        balances = value["leaveBalances"]
        self.require(name + "_balance", len(balances) == 1
                     and Decimal(balances[0]["usedDays"]) == Decimal(used)
                     and Decimal(balances[0]["pendingDays"]) == Decimal(pending)
                     and Decimal(balances[0]["availableDays"])
                     == 15 - Decimal(used) - Decimal(pending))
        events = value["teamLeaves"]
        self.require(name + "_calendar", events == [] if event is None else
                     len(events) == 1 and events[0]["status"] == event
                     and events[0]["employee"]["id"] == IDS[0])

    def execute(self, password: str, year: int) -> None:
        for actor, employee_id in zip(ACTORS, IDS, strict=True):
            value = self.request("login_" + actor, actor, "POST", "/auth/login",
                                 json={"email": f"staging.{actor}@jhworks.test",
                                       "password": password})
            self.require("identity_" + actor, value["employee"]["id"] == employee_id)
            me = self.request("session_" + actor, actor, "GET", "/employees/me")
            self.require("session_identity_" + actor, me["id"] == employee_id)
            self.require("role_" + actor, me["role"] == (
                "MANAGER" if actor == "approver" else "EMPLOYEE"))
            if actor != "approver":
                self.require("manager_" + actor, me["manager"]["id"] == IDS[1])
            for scope in ("mine", "assigned"):
                listing = self.request("initial_" + actor + "_" + scope, actor, "GET",
                                       "/approvals", params={"scope": scope})
                self.require("empty_" + actor + "_" + scope,
                             listing["items"] == [] and listing["total"] == 0)
        first = date(year, 12, 1)
        day = (first + timedelta(days=(-first.weekday()) % 7)).isoformat()
        self.overview("initial_leave", day, "0", "0", None)
        self.request("csrf_rejected", "author", "POST", "/auth/logout", 403,
                     headers={"Origin": "https://untrusted.invalid"})
        self.request("csrf_session_preserved", "author", "GET", "/employees/me")
        for kind in ("GENERAL", "LEAVE"):
            details: dict[str, Any] = {"kind": kind}
            if kind == "LEAVE":
                details.update(leaveType="ANNUAL", leaveUnit="FULL_DAY", startDate=day,
                               endDate=day, requestedDays="99.0", reason="Synthetic validation")
            prefix = kind.lower()
            draft = self.request(prefix + "_create", "author", "POST", "/approvals", 201,
                                 json={"type": kind, "title": "Private synthetic " + kind,
                                       "content": "Synthetic staging HTTP workflow validation.",
                                       "details": details, "attachmentMetadata": []})
            self.require(prefix + "_draft", draft["status"] == "DRAFT")
            path = "/approvals/" + draft["id"]
            if kind == "LEAVE":
                self.require("server_calculated_days",
                             Decimal(draft["details"]["requestedDays"]) == Decimal("1"))
            submitted = self.request(prefix + "_submit", "author", "POST", path + "/submit",
                                     json={"version": draft["version"]})
            self.require(prefix + "_pending", submitted["status"] == "PENDING"
                         and len(submitted["lines"]) == 1
                         and submitted["lines"][0]["approver"]["id"] == IDS[1])
            if kind == "LEAVE":
                self.overview("reserved_leave", day, "0", "1", "TENTATIVE")
            denied = self.request(prefix + "_unrelated_read", "unrelated", "GET", path, 403)
            self.require(prefix + "_read_forbidden", denied["error"]["code"] == "FORBIDDEN")
            self.request(prefix + "_unrelated_decide", "unrelated", "POST", path + "/approve",
                         403, json={"version": submitted["version"]})
            stale = self.request(prefix + "_stale", "approver", "POST", path + "/approve",
                                 409, json={"version": draft["version"]})
            self.require(prefix + "_conflict", stale["error"]["code"] == "VERSION_CONFLICT")
            unchanged = self.request(prefix + "_denied_state", "author", "GET", path)
            self.require(prefix + "_denied_unchanged", unchanged["status"] == "PENDING"
                         and unchanged["version"] == submitted["version"])
            approved = self.request(prefix + "_approve", "approver", "POST", path + "/approve",
                                    json={"version": submitted["version"],
                                          "comment": "Synthetic staging validation"})
            self.require(prefix + "_approved", approved["status"] == "APPROVED"
                         and approved["lines"][0]["status"] == "APPROVED")
            persisted = self.request(prefix + "_persisted", "author", "GET", path)
            self.require(prefix + "_persisted_state", persisted["status"] == "APPROVED"
                         and persisted["version"] == approved["version"])
        self.overview("confirmed_leave", day, "1", "0", "CONFIRMED")
        for actor in ACTORS:
            self.request("logout_" + actor, actor, "POST", "/auth/logout")
            self.request("logout_boundary_" + actor, actor, "GET", "/employees/me", 401)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    stage = "service_verify"
    workflow: Workflow | None = None
    try:
        verify_private_service(args.commit)
        if not args.apply:
            print(json.dumps({"status": "passed", "mode": "service-preflight", "changed": 0}))
            return
        stage = "operator_confirmation"
        if not sys.stdin.isatty():
            raise ValueError("interactive operator terminal required")
        print("Scope: create two synthetic approvals and use one fixture leave day.")
        stage = "credential_input"
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("Existing private fixture password (hidden): ")
        workflow = Workflow({})
        workflow.run_remote(password, args.commit)
        print(json.dumps({"status": "passed", "commit": args.commit,
                          "checks": workflow.passed, "createdApprovals": 2, "usedLeaveDays": 1}))
    except Exception as error:
        # HTTP exceptions can retain credentials/request bodies. Emit no raw exception.
        print(json.dumps({"status": "failed", "stage": workflow.stage if workflow else stage,
                          "errorType": type(error).__name__,
                          "checks": workflow.passed if workflow else []}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
