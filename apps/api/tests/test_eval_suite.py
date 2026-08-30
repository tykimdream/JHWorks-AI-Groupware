import json
import subprocess

from app.evals.suite import EvalCapability, build_report, interpret_result


def _capability(minimum_pass_rate: float = 1.0) -> EvalCapability:
    return EvalCapability.model_validate(
        {
            "name": "leave-assistant",
            "module": "app.evals.leave_assistant",
            "minimumPassRate": minimum_pass_rate,
        }
    )


def test_interpret_result_applies_quality_threshold_and_metrics() -> None:
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=json.dumps(
            {
                "summary": {"passed": 2, "total": 2},
                "results": [
                    {"latencyMs": 20, "totalTokens": 100},
                    {"latencyMs": 35, "totalTokens": 120},
                ],
            }
        ),
        stderr="",
    )

    outcome = interpret_result(_capability(), completed, duration_ms=60)

    assert outcome.status == "passed"
    assert outcome.pass_rate == 1.0
    assert outcome.p95_latency_ms == 35
    assert outcome.total_tokens == 220


def test_interpret_result_fails_when_required_case_fails() -> None:
    capability = _capability(0.5).model_copy(
        update={"required_case_ids": ["safety-case"]}
    )
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout=json.dumps(
            {
                "summary": {"passed": 1, "total": 2},
                "results": [
                    {"id": "quality-case", "passed": True},
                    {"id": "safety-case", "passed": False},
                ],
            }
        ),
        stderr="",
    )

    outcome = interpret_result(capability, completed, duration_ms=10)

    assert outcome.status == "failed"
    assert outcome.required_cases_passed is False
    assert outcome.failed_required_case_ids == ["safety-case"]


def test_interpret_result_rejects_invalid_or_unavailable_output() -> None:
    invalid = interpret_result(
        _capability(),
        subprocess.CompletedProcess(args=[], returncode=1, stdout="not-json", stderr="secret"),
        duration_ms=10,
    )
    unavailable = interpret_result(
        _capability(),
        subprocess.CompletedProcess(args=[], returncode=2, stdout="missing key", stderr=""),
        duration_ms=10,
    )

    assert invalid.status == "invalid_report"
    assert invalid.report is None
    assert unavailable.status == "unavailable"


def test_build_report_fails_when_any_capability_misses_threshold() -> None:
    passed = interpret_result(
        _capability(0.5),
        subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"summary": {"passed": 1, "total": 2}}),
            stderr="",
        ),
        duration_ms=10,
    )
    failed = interpret_result(
        _capability(),
        subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout=json.dumps({"passed": 1, "total": 2, "cases": []}),
            stderr="",
        ),
        duration_ms=10,
    )

    report = build_report([passed, failed])

    assert report["summary"]["status"] == "failed"
    assert report["summary"]["capabilitiesPassed"] == 1
    assert report["summary"]["casesPassed"] == 2
    assert report["summary"]["casesTotal"] == 4


def test_interpret_result_uses_manifest_threshold_not_child_exact_exit() -> None:
    outcome = interpret_result(
        _capability(0.5),
        subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout=json.dumps({"summary": {"passed": 1, "total": 2}}),
            stderr="",
        ),
        duration_ms=10,
    )

    assert outcome.status == "passed"
