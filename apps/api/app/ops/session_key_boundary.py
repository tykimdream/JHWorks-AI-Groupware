"""Inspect deployed session references; explicitly opt in to in-memory key checks.

No HTTP requests, employee reads, writes, key changes or emitted tokens. This
verifies real Secret key separation, not live service HTTP authentication.
"""

import argparse
import hmac
import json
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import jwt

PROJECT = "jhworks-staging-tykimdream"
REGION = "asia-northeast3"
TARGETS = {
    "jhworks-staging": ("jhworks-runtime", "jhworks-session-secret"),
    "jhworks-demo": ("jhworks-demo-runtime", "jhworks-demo-session-secret"),
}


def command(arguments: list[str]) -> str:
    return subprocess.run(
        ["gcloud", *arguments], capture_output=True, check=True, timeout=30,
    ).stdout.decode("utf-8")


def inspect_references(run: Callable[[list[str]], str]) -> list[str]:
    secrets = []
    for service, (account, secret) in TARGETS.items():
        options = ["--project=" + PROJECT, "--region=" + REGION, "--format=json"]
        state = json.loads(run(["run", "services", "describe", service, *options]))
        spec = state["spec"]["template"]["spec"]
        if spec["serviceAccountName"] != f"{account}@{PROJECT}.iam.gserviceaccount.com":
            raise ValueError("Unexpected runtime identity")
        if state["metadata"].get("annotations", {}).get(
            "run.googleapis.com/invoker-iam-disabled"
        ) == "true":
            raise ValueError("Service must remain private")
        ready = state["status"]["latestReadyRevisionName"]
        active = [(r.get("revisionName"), r.get("percent", 0))
                  for r in state["status"]["traffic"] if r.get("percent", 0)]
        if state["spec"]["template"]["metadata"]["name"] != ready or active != [(ready, 100)]:
            raise ValueError("Expected one current ready revision")
        api = next(c for c in spec["containers"] if c["name"] == "api")
        env = {e["name"]: e for e in api["env"]}
        if env["JHWORKS_AI_ENABLED"].get("value") != "false":
            raise ValueError("AI must remain disabled")
        if env.get("JHWORKS_JWT_ALGORITHM", {}).get("value", "HS256") != "HS256":
            raise ValueError("Expected the deployed HS256 algorithm")
        ref = env["JHWORKS_JWT_SECRET"]["valueFrom"]["secretKeyRef"]
        if ref != {"name": secret, "key": "1"}:
            raise ValueError("Unexpected session Secret reference")
        policy = json.loads(run(["run", "services", "get-iam-policy", service, *options]))
        if any(member in {"allUsers", "allAuthenticatedUsers"}
               for binding in policy.get("bindings", []) for member in binding.get("members", [])):
            raise ValueError("Public service policy is not allowed")
        secrets.append(secret)
    return secrets


def verify_keys(keys: list[str]) -> dict[str, int | bool]:
    if len(keys) != 2 or any(len(key) < 32 for key in keys):
        raise ValueError("Two strong session keys are required")
    if hmac.compare_digest(keys[0].encode(), keys[1].encode()):
        raise ValueError("Session keys must be distinct")
    now = int(datetime.now(UTC).timestamp())
    claims = {"sub": "synthetic-boundary-" + uuid4().hex,
              "type": "session", "iat": now, "exp": now + 60}
    tokens = [jwt.encode(claims, key, algorithm="HS256") for key in keys]
    rejected = 0
    for index, token in enumerate(tokens):
        if jwt.decode(token, keys[index], algorithms=["HS256"]) != claims:
            raise ValueError("Own-key validation failed")
        try:
            jwt.decode(token, keys[1 - index], algorithms=["HS256"])
        except jwt.InvalidSignatureError:
            rejected += 1
        else:
            raise ValueError("Cross-key validation unexpectedly succeeded")
    return {"distinctKeys": True, "ownSignaturesAccepted": 2, "crossSignaturesRejected": rejected}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-keys", action="store_true",
                        help="Read only the two fixed session Secret v1 payloads into memory")
    args = parser.parse_args()
    stage = "service_references"
    report: dict[str, Any] = {"status": "failed", "secretPayloadsRead": 0,
                              "httpRequests": 0, "writes": 0}
    try:
        secrets = inspect_references(command)
        report["serviceReferencesVerified"] = 2
        if args.verify_keys:
            stage = "session_keys"
            keys = []
            for secret in secrets:
                value = command(["secrets", "versions", "access", "1", "--secret=" + secret,
                                 "--project=" + PROJECT])
                report["secretPayloadsRead"] += 1
                # Preserve exact bytes represented by the stored text; stripping
                # whitespace could make the probe differ from the deployed key.
                keys.append(value)
            report.update(verify_keys(keys))
        report.update(status="passed", stage="complete", keysVerified=args.verify_keys)
    except Exception as exc:
        report.update(stage=stage, errorType=type(exc).__name__)
    print(json.dumps(report))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
