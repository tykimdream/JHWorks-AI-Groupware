from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response

from app.api.dependencies import CurrentEmployee, DbSession, get_ai_capabilities
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.security import create_session_token
from app.models.demo_workspace import DemoWorkspace
from app.models.employee import Employee
from app.schemas.demo import AICapabilities, DemoConfiguration, DemoRoleRequest, DemoVisitRead
from app.services.demo_visitor import start_visit_safely, switch_role
from app.services.mappers import current_employee_read

router = APIRouter(prefix="/demo", tags=["인증·체험"])


def _require_enabled() -> None:
    if not get_settings().public_demo_enabled:
        raise NotFoundError("Demo")


def _visit_response(db: DbSession, response: Response, actor: Employee) -> DemoVisitRead:
    settings = get_settings()
    workspace = db.get(DemoWorkspace, actor.demo_workspace_id)
    if workspace is None:
        raise NotFoundError("Demo workspace")
    response.set_cookie(
        settings.session_cookie_name,
        create_session_token(actor.id, datetime.fromtimestamp(workspace.expires_at_epoch, UTC)),
        max_age=settings.demo_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        path="/",
    )
    return DemoVisitRead(
        employee=current_employee_read(actor), expires_at_epoch=workspace.expires_at_epoch
    )


@router.get("/configuration", response_model=DemoConfiguration, summary="체험 설정 조회")
def configuration(
    ai_capabilities: Annotated[AICapabilities, Depends(get_ai_capabilities)],
) -> DemoConfiguration:
    """
    공개 체험 활성화 여부와 이용 시간·공간별 쓰기·보호 요청 제한을
    조회합니다. aiCapabilities는 서버 설정에 따른 기능별 AI 사용 가능
    여부입니다. 실제 요청은 권한·유효 세션·현재 provider 상태를 다시 확인합니다.
    """
    settings = get_settings()
    return DemoConfiguration(
        enabled=settings.public_demo_enabled,
        duration_minutes=settings.demo_ttl_minutes,
        ai_capabilities=ai_capabilities,
    )


@router.post("/start", response_model=DemoVisitRead, summary="체험 시작")
def start(
    db: DbSession,
    response: Response,
    session_token: Annotated[str | None, Cookie(alias=get_settings().session_cookie_name)] = None,
) -> DemoVisitRead:
    """
    합성 조직과 직원이 있는 방문자 전용 공간을 만들고 작성자 세션을
    발급합니다. 유효한 체험 세션이 있으면 해당 공간을 이어서
    사용합니다.
    """
    _require_enabled()
    actor = start_visit_safely(db, get_settings(), session_token)
    return _visit_response(db, response, actor)


@router.post("/role", response_model=DemoVisitRead, summary="체험 역할 전환")
def role(
    payload: DemoRoleRequest, db: DbSession, response: Response, actor: CurrentEmployee
) -> DemoVisitRead:
    """
    같은 체험 공간에서 작성자와 결재자 역할을 전환합니다. 다른 방문자의
    공간에는 접근할 수 없습니다.
    """
    _require_enabled()
    return _visit_response(db, response, switch_role(db, actor, payload.role))
