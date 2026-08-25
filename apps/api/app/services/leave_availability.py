from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attendance import LeaveAccount, WorkCalendarEvent
from app.models.employee import Employee
from app.models.enums import (
    AttendanceEventCategory,
    AttendanceEventStatus,
    AttendanceImpact,
    LeaveAvailabilityReasonCode,
    LeaveAvailabilityStatus,
    LeaveCandidateStatus,
)
from app.schemas.attendance import (
    LeaveAvailabilityCandidateRead,
    LeaveAvailabilityDayRead,
    LeaveAvailabilityRead,
    LeaveAvailabilityReasonRead,
    LeaveBalanceRead,
)
from app.services.leave_calendar import (
    confirmed_holiday_dates,
    dates_between,
    get_shared_events,
    get_team_leave_events,
)


@dataclass(frozen=True)
class DayAssessment:
    date: date
    is_workday: bool
    reasons: tuple[LeaveAvailabilityReasonRead, ...]

    @property
    def is_selectable(self) -> bool:
        return self.is_workday and not any(
            reason.impact == AttendanceImpact.BLOCKED for reason in self.reasons
        )


def find_leave_availability(
    db: Session,
    actor: Employee,
    start_date: date,
    end_date: date,
    requested_days: Decimal,
    limit: int,
) -> LeaveAvailabilityRead:
    shared_events = get_shared_events(db, actor, start_date, end_date)
    team_leave_events = get_team_leave_events(db, actor, start_date, end_date)
    holiday_dates = confirmed_holiday_dates(shared_events, start_date, end_date)
    assessments = [
        _assess_day(actor, current, holiday_dates, shared_events, team_leave_events)
        for current in dates_between(start_date, end_date)
    ]
    day_reads = [
        LeaveAvailabilityDayRead(
            date=item.date,
            is_workday=item.is_workday,
            is_selectable=item.is_selectable,
            reasons=list(item.reasons),
        )
        for item in assessments
    ]

    account = db.scalar(
        select(LeaveAccount).where(
            LeaveAccount.employee_id == actor.id,
            LeaveAccount.year == start_date.year,
        )
    )
    balance = _balance_read(account) if account is not None else None
    if account is None:
        return _response(
            status=LeaveAvailabilityStatus.ACCOUNT_UNAVAILABLE,
            start_date=start_date,
            end_date=end_date,
            requested_days=requested_days,
            balance=None,
            days=day_reads,
            reasons=[
                _reason(
                    LeaveAvailabilityReasonCode.ACCOUNT_UNAVAILABLE,
                    AttendanceImpact.BLOCKED,
                    f"{start_date.year}년 휴가 계정이 없어 후보를 계산할 수 없습니다.",
                )
            ],
        )
    if account.available_days < requested_days:
        return _response(
            status=LeaveAvailabilityStatus.INSUFFICIENT_BALANCE,
            start_date=start_date,
            end_date=end_date,
            requested_days=requested_days,
            balance=balance,
            days=day_reads,
            reasons=[
                _reason(
                    LeaveAvailabilityReasonCode.INSUFFICIENT_BALANCE,
                    AttendanceImpact.BLOCKED,
                    f"가용 연차 {account.available_days}일보다 "
                    f"{requested_days}일을 더 많이 요청했습니다.",
                )
            ],
        )

    candidates = _candidate_windows(assessments, requested_days)
    candidates.sort(
        key=lambda candidate: (
            0 if candidate.status == LeaveCandidateStatus.AVAILABLE else 1,
            len(candidate.reasons),
            candidate.start_date,
        )
    )
    candidates = candidates[:limit]
    if not candidates:
        return _response(
            status=LeaveAvailabilityStatus.NO_CANDIDATE,
            start_date=start_date,
            end_date=end_date,
            requested_days=requested_days,
            balance=balance,
            days=day_reads,
            reasons=[
                _reason(
                    LeaveAvailabilityReasonCode.NO_CANDIDATE,
                    AttendanceImpact.BLOCKED,
                    "선택한 탐색 범위에서 요청 일수를 충족하는 후보를 찾지 못했습니다.",
                )
            ],
        )

    return LeaveAvailabilityRead(
        status=LeaveAvailabilityStatus.READY,
        range_start=start_date,
        range_end=end_date,
        requested_days=requested_days,
        leave_balance=balance,
        candidates=candidates,
        days=day_reads,
        reasons=[],
    )


def _assess_day(
    actor: Employee,
    current: date,
    holiday_dates: set[date],
    shared_events: list[WorkCalendarEvent],
    team_leave_events: list[WorkCalendarEvent],
) -> DayAssessment:
    reasons: list[LeaveAvailabilityReasonRead] = []
    if current.weekday() >= 5:
        reasons.append(
            _reason(
                LeaveAvailabilityReasonCode.WEEKEND,
                AttendanceImpact.BLOCKED,
                "주말은 연차 차감일에서 제외됩니다.",
            )
        )

    for event in shared_events:
        if not event.start_date <= current <= event.end_date:
            continue
        if (
            event.category == AttendanceEventCategory.HOLIDAY
            and event.status == AttendanceEventStatus.CONFIRMED
        ):
            reasons.append(
                _reason(
                    LeaveAvailabilityReasonCode.HOLIDAY,
                    AttendanceImpact.BLOCKED,
                    f"확정 휴무일: {event.title}",
                    [event.id],
                )
            )
            continue
        impact = _effective_event_impact(event)
        if impact == AttendanceImpact.NONE:
            continue
        code = (
            LeaveAvailabilityReasonCode.PROJECT_MILESTONE
            if event.category == AttendanceEventCategory.PROJECT_MILESTONE
            else LeaveAvailabilityReasonCode.COMPANY_EVENT
        )
        reasons.append(_reason(code, impact, event.title, [event.id]))

    overlapping_leaves = [
        event for event in team_leave_events if event.start_date <= current <= event.end_date
    ]
    own_leaves = [event for event in overlapping_leaves if event.employee_id == actor.id]
    colleague_leaves = [event for event in overlapping_leaves if event.employee_id != actor.id]
    if own_leaves:
        reasons.append(
            _reason(
                LeaveAvailabilityReasonCode.OWN_LEAVE,
                AttendanceImpact.BLOCKED,
                "이미 신청했거나 승인된 본인 휴가와 겹칩니다.",
                [event.id for event in own_leaves],
            )
        )
    if colleague_leaves:
        reasons.append(
            _reason(
                LeaveAvailabilityReasonCode.TEAM_LEAVE,
                AttendanceImpact.CAUTION,
                f"같은 팀 휴가 {len(colleague_leaves)}건과 겹칩니다.",
                [event.id for event in colleague_leaves],
            )
        )

    return DayAssessment(
        date=current,
        is_workday=current.weekday() < 5 and current not in holiday_dates,
        reasons=tuple(reasons),
    )


def _effective_event_impact(event: WorkCalendarEvent) -> AttendanceImpact:
    if (
        event.status == AttendanceEventStatus.TENTATIVE
        and event.impact == AttendanceImpact.BLOCKED
    ):
        return AttendanceImpact.CAUTION
    return event.impact


def _candidate_windows(
    assessments: list[DayAssessment],
    requested_days: Decimal,
) -> list[LeaveAvailabilityCandidateRead]:
    required_workdays = 1 if requested_days == Decimal("0.5") else int(requested_days)
    candidates: list[LeaveAvailabilityCandidateRead] = []
    for index, first in enumerate(assessments):
        if not first.is_selectable:
            continue
        selected: list[DayAssessment] = []
        for item in assessments[index:]:
            if not item.is_workday:
                continue
            if not item.is_selectable:
                break
            selected.append(item)
            if len(selected) == required_workdays:
                candidates.append(_candidate_read(selected, requested_days))
                break
    return candidates


def _candidate_read(
    selected: list[DayAssessment],
    requested_days: Decimal,
) -> LeaveAvailabilityCandidateRead:
    caution_reasons = _unique_reasons(
        reason
        for item in selected
        for reason in item.reasons
        if reason.impact == AttendanceImpact.CAUTION
    )
    status = (
        LeaveCandidateStatus.CAUTION
        if caution_reasons
        else LeaveCandidateStatus.AVAILABLE
    )
    reasons = caution_reasons or [
        _reason(
            LeaveAvailabilityReasonCode.NO_CONFLICT,
            AttendanceImpact.NONE,
            "등록된 필수 일정이나 팀 휴가 충돌이 없습니다.",
        )
    ]
    return LeaveAvailabilityCandidateRead(
        start_date=selected[0].date,
        end_date=selected[-1].date,
        work_dates=[item.date for item in selected],
        requested_days=requested_days,
        status=status,
        reasons=reasons,
    )


def _unique_reasons(
    reasons: Iterable[LeaveAvailabilityReasonRead],
) -> list[LeaveAvailabilityReasonRead]:
    unique: dict[tuple[object, object, str, tuple[str, ...]], LeaveAvailabilityReasonRead] = {}
    for reason in reasons:
        key = (reason.code, reason.impact, reason.message, tuple(reason.event_ids))
        unique[key] = reason
    return list(unique.values())


def _balance_read(account: LeaveAccount) -> LeaveBalanceRead:
    return LeaveBalanceRead(
        year=account.year,
        granted_days=account.granted_days,
        carried_over_days=account.carried_over_days,
        used_days=account.used_days,
        pending_days=account.pending_days,
        available_days=account.available_days,
        version=account.version,
        updated_at=account.updated_at,
    )


def _reason(
    code: LeaveAvailabilityReasonCode,
    impact: AttendanceImpact,
    message: str,
    event_ids: list[str] | None = None,
) -> LeaveAvailabilityReasonRead:
    return LeaveAvailabilityReasonRead(
        code=code,
        impact=impact,
        message=message,
        event_ids=event_ids or [],
    )


def _response(
    status: LeaveAvailabilityStatus,
    start_date: date,
    end_date: date,
    requested_days: Decimal,
    balance: LeaveBalanceRead | None,
    days: list[LeaveAvailabilityDayRead],
    reasons: list[LeaveAvailabilityReasonRead],
) -> LeaveAvailabilityRead:
    return LeaveAvailabilityRead(
        status=status,
        range_start=start_date,
        range_end=end_date,
        requested_days=requested_days,
        leave_balance=balance,
        candidates=[],
        days=days,
        reasons=reasons,
    )
