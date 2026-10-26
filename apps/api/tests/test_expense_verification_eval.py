from app.evals.expense_verification import evaluate


def test_required_offline_expense_verification_cases_pass() -> None:
    result = evaluate()
    assert result["passed"] is True
    assert result["modelCalls"] == 0
    cases = result["cases"]
    assert isinstance(cases, list) and len(cases) == 8


def test_offline_entrypoint_does_not_import_database_settings_or_sdk() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; from app.evals.expense_verification import evaluate; "
                "assert evaluate()['passed']; "
                "assert 'app.core.database' not in sys.modules; "
                "assert 'app.core.config' not in sys.modules; "
                "assert 'openai' not in sys.modules"
            ),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
