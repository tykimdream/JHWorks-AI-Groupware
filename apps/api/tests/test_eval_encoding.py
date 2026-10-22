import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.evals.suite import EvalCapability, run_capability


def test_datasets_load_without_implicit_text_encoding() -> None:
    # Disabling UTF-8 mode reproduces cp949 on Korean Windows. EncodingWarning
    # makes the implicit-default regression observable on UTF-8 Linux as well.
    code = """
import importlib
from app.evals.suite import load_manifest
modules = ['approval_review', 'approval_draft', 'leave_assistant',
           'work_assistant', 'policy_retrieval']
counts = [len(importlib.import_module('app.evals.' + name).load_cases()) for name in modules]
assert all(counts)
assert len(load_manifest().capabilities) == len(modules)
print('datasets-loaded')
"""
    completed = subprocess.run(
        [sys.executable, "-X", "utf8=0", "-X", "warn_default_encoding",
         "-W", "error::EncodingWarning", "-c", code],
        cwd=Path(__file__).parents[1],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    assert completed.stdout.strip() == "datasets-loaded"


def test_suite_reads_utf8_child_report_without_provider_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = {"summary": {"passed": 1, "total": 1}, "results": [{"message": "합성 검증"}]}
    (tmp_path / "synthetic_eval.py").write_text(
        "import json\nprint(json.dumps(" + repr(report) + ", ensure_ascii=False))\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    outcome = run_capability(
        EvalCapability(name="synthetic", module="synthetic_eval", minimum_pass_rate=1),
        timeout_seconds=10,
    )
    assert outcome.status == "passed"
    assert json.dumps(outcome.report, ensure_ascii=False) == json.dumps(report, ensure_ascii=False)
