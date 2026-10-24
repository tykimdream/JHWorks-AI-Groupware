# API 안내

JHWorks는 FastAPI 모듈형 모놀리스다. `/api/v1` 아래에서 도메인별 REST API와 확인 기반 AI 명령을 제공한다.
API 경로·입력·응답 스키마의 원본은 [라우터](../../apps/api/app/api/router.py)와 Pydantic schema다.

## Swagger에서 읽기

- 공개 Swagger: **https://groupware.pikan.dev/api/v1/docs**
- 공개 OpenAPI JSON: **https://groupware.pikan.dev/api/v1/openapi.json**
- 로컬 API: `pnpm dev:api` → http://127.0.0.1:8000/api/v1/docs
- `/docs`와 `/openapi.json`은 새 경로로 이동한다. ReDoc은 `/api/v1/redoc`이다.

Swagger는 위 7개 업무 도메인으로 분류한다. 같은 API를 여러 그룹에 중복 표시하지 않으며, 각 항목에는 한글 제목·동작 설명·요청/응답 모델을 제공한다. 검색창은 도메인 이름을 필터링한다. 상세 endpoint는 도메인을 펼치거나 브라우저 찾기(Ctrl/Cmd+F)로 찾는다.
공개 모드는 `Try it out`을 비활성화한다. 이는 문서 UI 설정이며 API 접근 통제는 세션·출처·권한 검증이 담당한다.
로컬 실행 버튼은 실제 API를 호출하고 데이터를 변경할 수 있다. 실제 개인정보나 회사 자료는 넣지 않는다.

## 도메인 지도

| 도메인 | 주요 경로 (`/api/v1` 생략) | 찾을 수 있는 기능 |
| --- | --- | --- |
| 전자결재 | `/approvals`, `/approval-draft-assistant` | 초안·제출·승인·반려, 경비 점검, AI 초안·검토 |
| 근태·휴가 | `/attendance`, `/leave-assistant`, `/leave-draft-tool`, `/leave-agent/runs` | 일정·연차·가능일, AI 상담, 단계별 저장·제출 확인 |
| 정책 | `/policies`, `/policies/search` | 정책 목록과 관련 섹션 검색 |
| 조직 | `/employees/me`, `/departments` | 현재 직원·직속 관리자와 부서 |
| 업무 도우미 | `/work-assistant/query` | 내 업무 조회와 도구 실행 기록 |
| 인증·체험 | `/auth`, `/demo` | 로그인·로그아웃, 체험 시작·역할 전환·의견 접수 |
| 운영 | `/health`, `/health/live`, `/health/ready` | 프로세스와 DB 연결 상태 |

세부 하위 경로·허용 메서드·요청 모델은 Swagger를 따른다. 표의 그룹 경로가 모두 직접 호출 가능한 endpoint는 아니다.

## 인증·권한·동시성

1. 공개 체험은 `POST /demo/start`, 로컬 계정은 `POST /auth/login`으로 세션을 발급받는다.
2. HttpOnly 쿠키를 브라우저가 자동 전달한다. 기본 로컬 이름은 `jhworks_session`, Hosting 공개 환경은 `__session`이다.
3. Swagger의 `SessionCookie` 자물쇠는 보호 API라는 뜻이다. Authorize에 쿠키 값을 붙여넣어 HttpOnly 쿠키를 설정할 수는 없다.
4. 브라우저 쓰기 요청은 신뢰하는 Origin/Referer 검사를 통과해야 한다. 로컬에서도 frontend origin 설정이 일치해야 한다.
5. 서버는 세션 직원·체험 공간·작성자/현재 결재자·상태·version을 다시 검사한다. 클라이언트가 임의 직원으로 대리 실행할 수 없다.
6. `version`은 서버의 낙관적 동시성 제어다. UI 낙관적 업데이트와는 다른 개념이다.

## 대표 경비 정산 요청

아래는 **로컬 합성 데이터용**이다. API 필드는 camelCase이며 금액은 정수 원 단위다.
초안은 미완성 상태도 허용하지만 제출 시 필수 지출 정보를 검사한다.

```http
POST /api/v1/approvals
Content-Type: application/json
Origin: http://localhost:3000
Cookie: jhworks_session=<로그인 응답으로 발급된 쿠키>
```

```json
{
  "type": "EXPENSE",
  "title": "CES 출장 경비 정산 (합성 예시)",
  "content": "가상 업무 경비이며 실제 영수증을 첨부하지 않았습니다.",
  "amount": 170000,
  "details": {
    "kind": "EXPENSE",
    "expenseDate": "2026-01-10",
    "merchant": "가상 CES 사용처",
    "category": "OTHER",
    "purpose": "CES 업무 출장 경비",
    "receiptReference": "SYNTHETIC-REFERENCE"
  },
  "attachmentMetadata": []
}
```

`201` 응답은 `id`, `status: DRAFT`, `version` 등을 포함한 `ApprovalRead`다.
응답의 실제 ID·version을 사용해 `POST /approvals/{id}/submit`에 `{"version": 1}` 형태로 요청한다.
`/demo/role`에서 `{"role":"manager"}`로 전환한 뒤, 제출 응답의 새 version을 `/approve`에 전달한다.
예시의 `1`을 고정해 후속 요청에 재사용하지 않는다. 저장·제출·승인은 각각 별도 쓰기다.

증빙 참조는 문자열이며 파일 첨부·영수증 OCR·원본 검증이 아니다.
누락/중복 후보는 서버 규칙 기반이며 중복 여부의 최종 판정이나 자율 제출 Agent가 아니다.

## 오류 읽기

도메인 오류의 형태는 다음과 같다. `error.code`로 분기하고 `requestId`로 로그를 찾는다.

```json
{"error":{"code":"FORBIDDEN","message":"You do not have permission for this action","details":null},"requestId":"example-request-id"}
```

| 상태 | 의미 |
| --- | --- |
| 401 | 로그인 없음·잘못된 세션·만료 등 인증 실패 |
| 403 | 작성자/결재자·공간·쓰기 출처 경계 위반 |
| 404 | 리소스/비활성 기능 없음 |
| 409 | 오래된 version·허용하지 않는 업무 상태·변경된 미리보기 등 |
| 422 | 필수 업무 정보 오류 또는 요청 schema 검증 오류 |
| 429 | 로그인·공간·요청 예산 등 한도. 적용되는 경우 Retry-After 확인 |
| 503 | DB 준비 실패·AI 제공자 불가 등 |

FastAPI의 요청 형식 검증 오류는 `{"detail":[...]}` 형식이다. 모든 422가 위 도메인 envelope를 쓰지는 않는다.
모든 endpoint가 모든 상태를 반환하는 것은 아니다. 자세한 경비 계약은 [경비 API](../engineering/expense-api-contract.md)를 참조한다.

## 코드에서 찾기

- [Router](../../apps/api/app/api/router.py): URL 그룹 조합
- [Dependencies](../../apps/api/app/api/dependencies.py): 세션·직원·DB·AI 제공자
- [Schemas](../../apps/api/app/schemas/): 입력/출력 계약
- [Services](../../apps/api/app/services/): 업무 규칙·트랜잭션
- [Models](../../apps/api/app/models/) / [Alembic](../../apps/api/alembic/versions/): 저장 구조·변경 이력
- [전체 아키텍처](../architecture/README.md): 배포·대표 업무·책임 경계
