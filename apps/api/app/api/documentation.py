"""Public contract metadata; no database access or provider calls."""

API_DESCRIPTION = """
가상 기업 JHWorks의 전자결재·근태·정책·AI 업무 API입니다.

### 처음 읽는 순서
1. **demo / auth**: 공개 체험 시작 또는 로컬 계정 로그인 → HttpOnly 세션 쿠키 발급.
2. **organization / approvals**: 현재 직원 확인 → 초안 작성 → 별도 제출 → 결재자 승인·반려.
3. **attendance / policies**: 서버가 계산한 연차·일정과 버전이 있는 정책 원문 조회.
4. **AI**: 의도 추출·근거 검색·미리보기 → 사용자 확인 후 저장. AI가 권한을 결정하지 않습니다.

### 인증과 쓰기 계약
- 보호 API는 `SessionCookie`가 필요합니다. 쿠키 이름은 실행 환경에 따라 달라집니다.
- 브라우저는 로그인/체험 시작 응답의 HttpOnly 쿠키를 자동 전달합니다.
  Swagger Authorize 입력창으로 HttpOnly 쿠키를 직접 설정할 수는 없습니다.
- 쓰기 요청의 Origin/Referer는 신뢰하는 프론트엔드 출처여야 합니다.
- 수정·제출·승인 명령은 `version`을 받으며 오래된 버전은 409로 거부합니다.
- 요청·응답 필드는 camelCase입니다. `X-Request-ID`로 응답과 서버 로그를 연결합니다.

### 공개 데모
공개 모드의 이 문서는 읽기 전용입니다(Try it out 비활성).
실제 API의 권한은 그대로 적용되며 문서 설정은 접근 통제가 아닙니다.
공개 AI는 꺼져 있고 AI 경로는 제공자 미사용/비활성 오류를 반환할 수 있습니다.
체험 세션 15분, 공간별 저장 시도 20회·보호 요청 100회,
전체 하루 시작 20회·보관 30공간 상한이 있습니다.
자동 정리는 비활성이라 보관 상한에 닿으면 새 체험이 중단됩니다.

[API 설계 안내](https://github.com/tykimdream/JHWorks-AI-Groupware/blob/main/docs/api/README.md)
· [전체 아키텍처](https://github.com/tykimdream/JHWorks-AI-Groupware/blob/main/docs/architecture/README.md)
"""

TAGS = [
    {
        "name": "health",
        "description": "프로세스 생존과 DB 준비 상태. 업무 데이터 조회와 분리합니다.",
    },
    {
        "name": "demo",
        "description": (
            "격리된 합성 체험 공간 발급·수명·역할 전환·의견 접수. "
            "공개 피드백 목록 조회는 없습니다."
        ),
    },
    {
        "name": "auth",
        "description": (
            "로컬/비공개 계정 로그인과 로그아웃. "
            "공개 모드는 비밀번호 로그인을 거부합니다."
        ),
    },
    {
        "name": "organization",
        "description": "현재 사용자와 조직·관리자 조회. 조직 범위는 서버에서 검증합니다.",
    },
    {
        "name": "approvals",
        "description": "일반·출장·경비·휴가 초안, 상태 전이, 경비 누락/중복 후보 점검과 AI 검토.",
    },
    {
        "name": "attendance",
        "description": "근태 캘린더·연차 계정·휴가 가능일을 결정적으로 계산합니다.",
    },
    {"name": "policies", "description": "버전·섹션 ID가 있는 가상 회사 정책과 검색 근거."},
    {
        "name": "approval-draft-assistant",
        "description": "일반·출장·경비 요청 구조화, 후속 질문, 서명된 미리보기 확인 후 DRAFT 저장.",
    },
    {
        "name": "leave-assistant",
        "description": "읽기 전용 휴가 상담. 연차·일정 계산은 서버가 담당합니다.",
    },
    {
        "name": "leave-draft-tool",
        "description": "휴가 미리보기와 명시적 확인을 통한 멱등 초안 저장.",
    },
    {
        "name": "leave-agent",
        "description": "지속되는 휴가 업무 상태와 초안/제출 각각의 사용자 확인.",
    },
    {
        "name": "work-assistant",
        "description": (
            "사용자 범위의 제한된 읽기 Tool과 실행 기록. "
            "임의 DB 쓰기는 허용하지 않습니다."
        ),
    },
]
