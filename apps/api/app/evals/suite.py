import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MANIFEST_PATH = Path(__file__).parents[2] / "evals" / "suite.json"
DEFAULT_OUTPUT_PATH = Path(__file__).parents[4] / "artifacts" / "evals" / "latest.json"


def _to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class EvalCapability(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="forbid",
    )

    name: str
    module: str
    minimum_pass_rate: float = Field(ge=0.0, le=1.0)
    required_case_ids: list[str] = Field(default_factory=list)


class EvalManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilities: list[EvalCapability] = Field(min_length=1)


class CapabilityOutcome(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="forbid",
    )

    name: str
    module: str
    status: Literal["passed", "failed", "unavailable", "invalid_report"]
    exit_code: int
    minimum_pass_rate: float
    passed: int | None = None
    total: int | None = None
    pass_rate: float | None = None
    duration_ms: int
    p95_latency_ms: int | None = None
    total_tokens: int | None = None
    required_cases_passed: bool | None = None
    failed_required_case_ids: list[str] = Field(default_factory=list)
    report: dict[str, Any] | None = None

def load_manifest(path: Path = MANIFEST_PATH) -> EvalManifest:
    return EvalManifest.model_validate_json(path.read_text())


def _case_results(report: dict[str, Any]) -> list[dict[str, Any]]:
    raw = report.get("results", report.get("cases", []))
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _summary_counts(report: dict[str, Any]) -> tuple[int, int] | None:
    raw_summary = report.get("summary", report)
    if not isinstance(raw_summary, dict):
        return None
    passed = raw_summary.get("passed")
    total = raw_summary.get("total")
    if not isinstance(passed, int) or not isinstance(total, int) or total <= 0:
        return None
    if passed < 0 or passed > total:
        return None
    return passed, total


def _nearest_rank_p95(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, ceil(len(ordered) * 0.95) - 1)]


def interpret_result(
    capability: EvalCapability,
    completed: subprocess.CompletedProcess[str],
    duration_ms: int,
) -> CapabilityOutcome:
    if completed.returncode == 2:
        return CapabilityOutcome(
            name=capability.name,
            module=capability.module,
            status="unavailable",
            exit_code=completed.returncode,
            minimum_pass_rate=capability.minimum_pass_rate,
            duration_ms=duration_ms,
        )

    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        return CapabilityOutcome(
            name=capability.name,
            module=capability.module,
            status="invalid_report",
            exit_code=completed.returncode,
            minimum_pass_rate=capability.minimum_pass_rate,
            duration_ms=duration_ms,
        )

    counts = _summary_counts(parsed)
    if counts is None:
        return CapabilityOutcome(
            name=capability.name,
            module=capability.module,
            status="invalid_report",
            exit_code=completed.returncode,
            minimum_pass_rate=capability.minimum_pass_rate,
            duration_ms=duration_ms,
            report=parsed,
        )

    passed, total = counts
    pass_rate = passed / total
    cases = _case_results(parsed)
    latencies = [
        value
        for item in cases
        if isinstance((value := item.get("latencyMs")), int)
    ]
    token_values = [
        value
        for item in cases
        if isinstance(
            (value := item.get("totalTokens", item.get("inputTokens"))), int
        )
    ]
    results_by_id = {
        str(item["id"]): item for item in cases if isinstance(item.get("id"), str)
    }
    failed_required_case_ids = [
        case_id
        for case_id in capability.required_case_ids
        if case_id not in results_by_id
        or results_by_id[case_id].get("passed", results_by_id[case_id].get("hit"))
        is not True
    ]
    required_cases_passed = not failed_required_case_ids
    status: Literal["passed", "failed"] = (
        "passed"
        if completed.returncode in {0, 1}
        and pass_rate >= capability.minimum_pass_rate
        and required_cases_passed
        else "failed"
    )
    return CapabilityOutcome(
        name=capability.name,
        module=capability.module,
        status=status,
        exit_code=completed.returncode,
        minimum_pass_rate=capability.minimum_pass_rate,
        passed=passed,
        total=total,
        pass_rate=pass_rate,
        duration_ms=duration_ms,
        p95_latency_ms=_nearest_rank_p95(latencies),
        total_tokens=sum(token_values) if token_values else None,
        required_cases_passed=required_cases_passed,
        failed_required_case_ids=failed_required_case_ids,
        report=parsed,
    )


def run_capability(
    capability: EvalCapability,
    timeout_seconds: int,
) -> CapabilityOutcome:
    started_at = perf_counter()
    try:
        completed = subprocess.run(
            [sys.executable, "-m", capability.module],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return CapabilityOutcome(
            name=capability.name,
            module=capability.module,
            status="unavailable",
            exit_code=2,
            minimum_pass_rate=capability.minimum_pass_rate,
            duration_ms=round((perf_counter() - started_at) * 1000),
        )
    return interpret_result(
        capability,
        completed,
        round((perf_counter() - started_at) * 1000),
    )


def build_report(outcomes: list[CapabilityOutcome]) -> dict[str, Any]:
    case_passed = sum(outcome.passed or 0 for outcome in outcomes)
    case_total = sum(outcome.total or 0 for outcome in outcomes)
    status_counts = {
        status: sum(outcome.status == status for outcome in outcomes)
        for status in ("passed", "failed", "unavailable", "invalid_report")
    }
    return {
        "schemaVersion": "1.0",
        "generatedAt": datetime.now(UTC).isoformat(),
        "summary": {
            "status": "passed"
            if status_counts == {
                "passed": len(outcomes),
                "failed": 0,
                "unavailable": 0,
                "invalid_report": 0,
            }
            else "failed",
            "capabilitiesPassed": status_counts["passed"],
            "capabilitiesTotal": len(outcomes),
            "casesPassed": case_passed,
            "casesTotal": case_total,
            "totalTokens": sum(outcome.total_tokens or 0 for outcome in outcomes),
            "statusCounts": status_counts,
        },
        "capabilities": [
            outcome.model_dump(by_alias=True, mode="json") for outcome in outcomes
        ],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run all external AI evaluations and emit one regression report."
    )
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--timeout-seconds", type=int, default=180)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.timeout_seconds < 1:
        raise SystemExit("--timeout-seconds must be positive")
    manifest = load_manifest(args.manifest)
    requested = set(args.only)
    capabilities = [
        capability
        for capability in manifest.capabilities
        if not requested or capability.name in requested
    ]
    unknown = requested - {capability.name for capability in manifest.capabilities}
    if unknown:
        raise SystemExit(f"Unknown evaluation capabilities: {', '.join(sorted(unknown))}")

    outcomes = [
        run_capability(capability, args.timeout_seconds) for capability in capabilities
    ]
    report = build_report(outcomes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if any(outcome.status == "unavailable" for outcome in outcomes):
        return 2
    return 0 if report["summary"]["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
