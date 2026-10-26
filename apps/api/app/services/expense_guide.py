"""Curated workflow help. No model, document writes, or inferred business policy."""

from app.models.enums import ApprovalStatus
from app.schemas.expense_guide import (
    ExpenseGuide,
    ExpenseGuideAnswer,
    ExpenseGuideField,
    ExpenseGuideStage,
)
from app.services.expense_validation import EXPENSE_REQUIRED_FIELDS

FIELD_COPY = {
    "expenseDate": (
        "실제 지출일",
        "실제로 결제한 날짜입니다. 미래 날짜는 제출할 수 없습니다.",
        "2026-01-08",
    ),
    "merchant": ("사용처", "돈을 지불한 상호나 대상을 입력합니다.", "코레일 서울역"),
    "category": ("비용 구분", "교통비·숙박비·식비·기타 중 실제 지출에 맞게 선택합니다.", "교통비"),
    "purpose": (
        "업무 목적",
        "어떤 업무를 위해 지출했는지 설명합니다. 출장명만으로 부족하면 실제 활동을 적으세요.",
        "CES 협력사 데모 시연 방문",
    ),
}


def expense_guide() -> ExpenseGuide:
    fields = [
        ExpenseGuideField(
            field="amount",
            label="실제 지출 금액",
            description="0원보다 큰 실제 지출 금액을 원 단위로 입력합니다.",
            example="170000",
            required=True,
        )
    ]
    fields.extend(
        ExpenseGuideField(
            field=f"details.{key}",
            label=FIELD_COPY[key][0],
            description=FIELD_COPY[key][1],
            example=FIELD_COPY[key][2],
            required=True,
        )
        for key in EXPENSE_REQUIRED_FIELDS
    )
    fields.append(
        ExpenseGuideField(
            field="details.receiptReference",
            label="증빙 참조",
            required=False,
            example="RCP-CES-001",
            description=(
                "원본을 찾기 위한 문서번호입니다. 파일 첨부나 영수증 진위 확인을 뜻하지 않습니다."
            ),
        )
    )
    return ExpenseGuide(
        fields=fields,
        stages=[
            ExpenseGuideStage(
                status=ApprovalStatus.DRAFT,
                title="초안",
                meaning="작성 중이며 아직 결재자에게 제출되지 않았습니다.",
                next_step=(
                    "작성자가 제목·업무 내용·필수 경비 정보를 보완하고 제출합니다. "
                    "활성 직속 관리자가 필요합니다."
                ),
            ),
            ExpenseGuideStage(
                status=ApprovalStatus.PENDING,
                title="결재 대기",
                meaning="지정 결재자에게 제출된 상태입니다. 작성자는 초안을 편집할 수 없습니다.",
                next_step=(
                    "현재 단계의 담당 결재자가 문서와 원본 증빙을 확인해 승인하거나 "
                    "사유를 적어 반려합니다."
                ),
            ),
            ExpenseGuideStage(
                status=ApprovalStatus.REJECTED,
                title="반려",
                meaning="결재자가 보완 사유와 함께 돌려보낸 상태입니다.",
                next_step=(
                    "작성자가 반려 의견을 확인하고 초안으로 전환해 수정합니다. "
                    "이력은 유지되며 제출은 다시 확인해야 합니다."
                ),
            ),
            ExpenseGuideStage(
                status=ApprovalStatus.APPROVED,
                title="승인",
                meaning="결재 승인이 완료됐습니다. 실제 송금이나 회계 전표 처리를 뜻하지 않습니다.",
                next_step=(
                    "결재 이력을 확인할 수 있습니다. 이 서비스에는 승인 후 송금 기능이 없습니다."
                ),
            ),
        ],
        questions=[
            ExpenseGuideAnswer(
                id="submit",
                question="저장과 제출은 어떻게 다른가요?",
                answer=(
                    "초안 저장은 작성 중인 내용을 보관합니다. 빠진 항목이 있어도 "
                    "저장할 수 있습니다. 제출은 제목·업무 내용·경비 필드와 "
                    "결재자를 서버가 검사한 뒤 진행하며 별도 확인이 필요합니다."
                ),
            ),
            ExpenseGuideAnswer(
                id="receipt",
                question="증빙 참조만 적으면 영수증이 확인되나요?",
                answer=(
                    "아니요. 참조는 원본을 찾기 위한 정보입니다. 현재 파일 "
                    "업로드·원본 진위 검증은 제공하지 않습니다. 결재자는 원본을 "
                    "별도로 확인해야 합니다. 금액별 기준은 현재 회사 규정에서 "
                    "확인하세요."
                ),
            ),
            ExpenseGuideAnswer(
                id="rejection",
                question="반려되면 처음부터 다시 작성해야 하나요?",
                answer=(
                    "같은 문서를 초안으로 전환해 보완할 수 있고 이전 반려 의견은 "
                    "유지됩니다. AI 수정 제안이 지원되는 환경에서도 새 사실을 "
                    "알려주고 변경 전후를 확인한 후 반영해야 합니다. 반영만으로 "
                    "제출되지는 않습니다."
                ),
            ),
            ExpenseGuideAnswer(
                id="approver",
                question="누가 승인하고 어떤 것을 확인하나요?",
                answer=(
                    "제출 시 작성자의 직속 관리자가 결재자로 지정됩니다. 현재 "
                    "담당자는 실제 지출 내용·원본 증빙·규정 기준·중복 후보를 "
                    "확인합니다. 자동 검사나 AI 제안이 승인을 대신하지 않습니다."
                ),
            ),
        ],
    )
