"""Small synthetic retrieval smoke test; this invokes the configured embedding provider."""

from datetime import date

from app.ai.approval_draft import ApprovalDraftProviderInput
from app.ai.openai_policy_embedding import OpenAIPolicyEmbeddingProvider
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.approval_examples import search_examples
from app.services.draft_privacy import mask_draft_input

# Requests are separate from the example bodies and cover distinct work types.
CASES = (
    (
        "서비스 기획을 위해 담당자들과 인터뷰한 내용을 정리해서 보고하려고 해",
        {"interview-report", "interview-process"},
    ),
    (
        "업무 절차의 불편함을 현업 인터뷰로 파악한 결과를 보고해줘",
        {"interview-process", "interview-report"},
    ),
    ("개발팀에 새 노트북 세 대를 구매하는 결재 요청을 작성해줘", {"purchase-request"}),
    ("디자인 소프트웨어 연간 라이선스 구독 승인을 요청해", {"software-purchase"}),
    ("신규 고객 데이터 이전 프로젝트를 시작하려고 해", {"project-start"}),
    ("진행 중인 프로젝트의 납기를 변경하는 결재를 작성해", {"project-change"}),
    ("다른 팀에게 분석용 자료를 제공해 달라고 요청해", {"data-request", "cooperation-request"}),
    ("협력사와 계약하기 전에 계약서 검토를 요청할래", {"contract-review"}),
    ("어제 발생한 서비스 장애의 조치 경과를 보고해", {"incident-report"}),
    ("사내 시스템에 접속할 수 있도록 권한 부여를 신청해", {"access-request"}),
    ("직무 역량 교육 참가를 승인받고 싶어", {"training-request"}),
    ("예산을 증액해야 해서 기존 금액과 변경 사유를 기안할래", {"budget-change"}),
)


def main() -> None:
    settings = get_settings()
    key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    if not key:
        raise SystemExit("JHWORKS_OPENAI_API_KEY is required")
    provider = OpenAIPolicyEmbeddingProvider(
        key,
        settings.policy_embedding_model,
        settings.policy_embedding_dimensions,
        settings.ai_review_timeout_seconds,
    )
    hits = 0
    with SessionLocal() as db:
        for query, expected in CASES:
            masked = mask_draft_input(
                ApprovalDraftProviderInput(
                    request=query, answers=[], current_date=date.today(), timezone="Asia/Seoul"
                )
            )
            status, rows = search_examples(
                db,
                provider,
                masked.topic_query or "일반 업무 기안",
                settings.policy_embedding_model,
                settings.policy_embedding_dimensions,
            )
            ids = [row.id for row in rows]
            hit = status == "READY" and bool(expected.intersection(ids))
            hits += int(hit)
            print(f"{'PASS' if hit else 'MISS'}: {query} => {', '.join(ids) or status}")
    print(f"top_two_hits={hits}/{len(CASES)}")


if __name__ == "__main__":
    main()
