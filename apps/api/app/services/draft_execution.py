"""Single prepare orchestration. No SDK, persistence, retries, or business writes."""

import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter
from typing import Literal
from uuid import uuid4

from app.ai.approval_draft import PROMPT_VERSION
from app.schemas.draft_execution import (
    DraftExecutionRead,
    DraftStage,
    DraftStageOutcome,
    DraftStageRecord,
)

logger = logging.getLogger("jhworks.draft_execution")
STAGES = tuple(DraftStage)


@dataclass
class StageResult:
    outcome: DraftStageOutcome = DraftStageOutcome.PASSED


class DraftExecution:
    def __init__(self, prompt_version: str = PROMPT_VERSION) -> None:
        self.prompt_version = prompt_version
        self.run_id = f"draft_run_{uuid4().hex}"
        self._started = perf_counter()
        self._records: list[DraftStageRecord] = []
        self._active = False
        self._finished = False
        self._provider: str | None = None
        self._model: str | None = None

    def provider_metadata(self, provider: str, model: str) -> None:
        if not self._active or len(self._records) != 1:
            raise RuntimeError("Provider metadata outside provider stage")
        # Model identifiers only; malformed vendor metadata is never echoed in diagnostics.
        allowed = r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}"
        self._provider = provider if re.fullmatch(allowed, provider) else None
        self._model = model if re.fullmatch(allowed, model) else None

    @contextmanager
    def stage(self, stage: DraftStage) -> Iterator[StageResult]:
        if (
            self._finished
            or self._active
            or len(self._records) >= len(STAGES)
            or any(r.outcome == DraftStageOutcome.FAILED for r in self._records)
            or stage != STAGES[len(self._records)]
        ):
            raise RuntimeError("Invalid draft execution transition")
        self._active = True
        started = perf_counter()
        result = StageResult()
        try:
            yield result
        except Exception:
            result.outcome = DraftStageOutcome.FAILED
            raise
        finally:
            self._records.append(
                DraftStageRecord(
                    stage=stage,
                    outcome=result.outcome,
                    duration_ms=max(0, round((perf_counter() - started) * 1000)),
                )
            )
            self._active = False

    def report(
        self, outcome: Literal["PREVIEW", "NEEDS_INPUT", "UNSUPPORTED", "FAILED"]
    ) -> DraftExecutionRead:
        if self._finished or self._active:
            raise RuntimeError("Draft execution already finished or still active")
        failed = any(r.outcome == DraftStageOutcome.FAILED for r in self._records)
        if outcome != "FAILED" and (failed or len(self._records) != len(STAGES)):
            raise RuntimeError("Incomplete draft execution cannot succeed")

        if outcome != "FAILED":
            expected = (
                DraftStageOutcome.PASSED if outcome == "PREVIEW" else DraftStageOutcome(outcome)
            )
            if self._records[3].outcome != expected:
                raise RuntimeError("Execution outcome contradicts validation")
            if outcome != "PREVIEW" and any(
                r.outcome != DraftStageOutcome.NOT_APPLICABLE for r in self._records[4:]
            ):
                raise RuntimeError("Unready draft cannot run policy or preview")
        return DraftExecutionRead(
            run_id=self.run_id,
            prompt_version=self.prompt_version,
            provider=self._provider,
            model=self._model,
            outcome=outcome,
            stages=self._records,
            duration_ms=max(0, round((perf_counter() - self._started) * 1000)),
        )

    def finish(
        self, outcome: Literal["PREVIEW", "NEEDS_INPUT", "UNSUPPORTED", "FAILED"]
    ) -> DraftExecutionRead:
        trace = self.report(outcome)
        self._finished = True
        # Deliberately exclude prompts, candidates, identity, tokens, and exception text.
        logger.info("draft_execution_finished execution=%s", trace.model_dump_json(by_alias=True))
        return trace
