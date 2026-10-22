import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.demo_feedback import DemoFeedback
from app.services import demo_feedback


def add_feedback(db: Session, name: str, created: int) -> None:
    db.add(
        DemoFeedback(
            id=name,
            workspace_hash=name.ljust(64, "0"),
            content_hash="a" * 64,
            category="idea",
            screen="general",
            message="Synthetic retention test message",
            created_at_epoch=created,
        )
    )


def test_retention_boundary_dry_run_and_repeated_apply(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 1800000000
    monkeypatch.setattr(demo_feedback, "database_seconds", lambda db: now)
    cutoff = now - demo_feedback.RETENTION_SECONDS
    with session_factory() as db:
        add_feedback(db, "old", cutoff - 1)
        add_feedback(db, "boundary", cutoff)
        add_feedback(db, "fresh", cutoff + 1)
        db.commit()
    with session_factory() as db:
        result = demo_feedback.purge_expired_feedback(db)
        assert (result.expired, result.removed, result.stored) == (2, 0, 3)
        assert not db.in_transaction()
    with session_factory() as db:
        result = demo_feedback.purge_expired_feedback(db, apply=True)
        assert (result.expired, result.removed, result.stored) == (2, 2, 1)
    with session_factory() as db:
        result = demo_feedback.purge_expired_feedback(db, apply=True)
        assert (result.expired, result.removed, result.stored) == (0, 0, 1)
        assert db.scalar(select(DemoFeedback.id)) == "fresh"


def test_commit_failure_rolls_back_deletion(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with session_factory() as db:
        add_feedback(db, "old", 1)
        db.commit()
    with session_factory() as db:

        def fail() -> None:
            raise RuntimeError("Synthetic commit failure")

        monkeypatch.setattr(db, "commit", fail)
        with pytest.raises(RuntimeError):
            demo_feedback.purge_expired_feedback(db, apply=True)
        assert not db.in_transaction()
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(DemoFeedback)) == 1


def test_retention_refuses_caller_transaction(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as db:
        add_feedback(db, "pending", 1)
        with pytest.raises(ValueError, match="fresh session"):
            demo_feedback.purge_expired_feedback(db, apply=True)
        assert len(db.new) == 1


def test_operator_failure_hides_message_and_does_not_report_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import json
    import sys

    from app.core.config import Settings
    from app.ops import demo_feedback as operator

    monkeypatch.setattr(
        operator,
        "get_settings",
        lambda: Settings(
            _env_file=None,
            public_demo_enabled=True,
            ai_enabled=False,
        ),
    )

    def fail(**kwargs: object) -> object:
        raise RuntimeError("Synthetic private failure text must not be printed")

    monkeypatch.setattr(operator, "SessionLocal", fail)
    monkeypatch.setattr(sys, "argv", ["feedback", "--purge-expired", "--apply"])
    with pytest.raises(SystemExit) as result:
        operator.main()
    assert result.value.code == 1
    assert json.loads(capsys.readouterr().out) == {
        "status": "failed",
        "errorType": "RuntimeError",
    }
