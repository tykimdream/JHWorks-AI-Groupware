"""API documentation grouped by business domain; no runtime behavior changes."""

API_DESCRIPTION = """
전자결재, 경비 정산, 근태·휴가와 회사 정책을 다루는 JHWorks API입니다.

**대표 흐름:** 체험 시작 → 경비 초안 저장 → 제출 → 결재자 역할 전환 → 승인.
아래에서 업무 도메인을 펼쳐 요청 형식과 응답 예시를 확인하세요. 검색창은 도메인 이름을 필터링합니다.

보호 API는 로그인 또는 체험 시작 시 발급된 세션 쿠키가 필요합니다.
수정·제출·승인 요청에는 현재 문서의 `version`을 전달합니다.
요청·응답 필드는 `camelCase`를 사용합니다.

**공개 데모:** 문서의 요청 실행 기능은 비활성화되어 있으며, 유료 AI 호출도 꺼져 있습니다.
직접 작성과 결재 흐름은 [라이브 데모](https://groupware.pikan.dev)에서 체험할 수 있습니다.

[인증·오류·요청 예시 안내](https://github.com/tykimdream/JHWorks-AI-Groupware/blob/main/docs/api/README.md)
· [아키텍처](https://github.com/tykimdream/JHWorks-AI-Groupware/blob/main/docs/architecture/README.md)
"""

TAGS = [
    {"name": "전자결재", "description": "초안 작성·제출·승인·반려, 경비 점검과 AI 초안·검토"},
    {"name": "근태·휴가", "description": "일정·연차 조회, 휴가 가능일과 상담·신청 진행"},
    {"name": "정책", "description": "회사 정책 원문과 관련 섹션 검색"},
    {"name": "조직", "description": "현재 직원·직속 관리자와 부서 조회"},
    {"name": "업무 도우미", "description": "AI를 통한 내 업무 조회와 실행 기록"},
    {"name": "인증·체험", "description": "로그인·로그아웃, 방문자 체험·역할 전환과 의견 접수"},
    {"name": "운영", "description": "API 프로세스와 DB 연결 상태 확인"},
]
