"""The benchmark refuses remote/overridable targets before any engine is created."""

from typing import Any

import pytest

from app.ops import approval_list_benchmark as benchmark


@pytest.mark.parametrize("raw", [
    "", "postgresql+psycopg://jhworks_test:x@remote.example/jhworks_test",
    "postgresql+psycopg://postgres:x@localhost/jhworks_test",
    "postgresql+psycopg://jhworks_test:x@localhost/production",
    "postgresql+psycopg://jhworks_test:x@localhost/jhworks_test?host=remote.example",
    "postgresql+psycopg://jhworks_test:x@localhost/jhworks_test?service=staging",
    "sqlite:///local.db",
])
def test_invalid_targets_do_not_create_engine(raw: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("an invalid target must never create an engine")

    monkeypatch.setattr(benchmark, "create_engine", forbidden)
    with pytest.raises(ValueError):
        benchmark.run(raw, [4], 1)


@pytest.mark.parametrize("raw", ["0", "10001", "4,4", "4,5,6,7", "bad", ""])
def test_unbounded_counts_are_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        benchmark.bounded_counts(raw)


def test_bounded_defaults_and_dedicated_target() -> None:
    assert benchmark.bounded_counts("100,1000") == [100, 1000]
    assert benchmark.dedicated_url(
        "postgresql+psycopg://jhworks_test:synthetic@127.0.0.1:5432/jhworks_test"
    ).host == "127.0.0.1"
