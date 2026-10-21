# 엔터프라이즈 고도화 진단 — 2026-10-21

이 문서의 본문은 최초 진단 시점의 snapshot이다. 후속 구현의 최신 상태는
[staging 실제 실행 기록](staging-rehearsal.md)과 [로드맵](roadmap.md)을 따른다.
2026-10-21 후속 private Cloud Run 기동·Supabase migration·수동 smoke 4개는 검증됐으나,
공개 데모와 CI release 전체 성공·업무 로그인/저장·backup/restore는 아직 검증되지 않았다.

## 기준과 결론

로컬 시작점은 `main`, HEAD `9814045`(PR #16 merge), working tree clean이었다.
origin은 `https://github.com/tykimdream/JHWorks-AI-Groupware.git`이다. 원격 fetch/push는 하지 않았으므로
원격 최신 HEAD와의 일치는 주장하지 않는다. 작업 브랜치는 기여 가이드 형식의 `fix/enterprise-csrf-boundary`다.

기존 Modular Monolith, AI 확인/멱등성, 업무 서비스와 CI를 유지한다. 공개 배포 준비는 **부분 구현**이다.
README의 기존 Phase 11 완료는 provider-neutral release 계약과 과거 로컬 rehearsal 완료를 의미하며,
외부 서비스 운영 완료를 의미하지 않는다. 이번 문서의 Phase 0~5는 새로운 고도화 단계다.

읽은 지침: 전체 검색에서 발견한 `apps/web/AGENTS.md`, `apps/web/CLAUDE.md`(@AGENTS.md),
`CONTRIBUTING.md`, `docs/code-conventions.md`, README, product phase 문서, ADR-0001,
release runbook, portfolio 검증 기록과 실제 소스·migration·테스트·CI 설정.
웹 지침은 해당 버전의 Next 내장 문서를 먼저 읽도록 요구한다. 이번 작업은 웹 소스를 바꾸지 않았다.

분류의 ‘검증 완료’는 아래에 명시한 로컬·합성 데이터·fake AI 범위만 의미한다.

## 아키텍처와 실제 구현

| 대상 | 분류 | 코드 근거와 판단 |
| --- | --- | --- |
| 앱/의존성 | 구현 및 검증 완료 | pnpm workspace(web), uv workspace(API). Next 16.3.8/React 19.2.8/TS 5.9.3, FastAPI/SQLAlchemy/Alembic, PostgreSQL+pgvector, SQLite. 기존 잠금 파일 유지, 새 라이브러리 없음 |
| App Router 경계 | 구현됐지만 추가 검증 필요 | `app/page.tsx`는 `/approvals` redirect. layout·일부 route는 Server Component, 업무 목록/상세·폼·AI는 Client Component. Server Component로 업무 조회를 옮긴 구조는 아님 |
| 상태와 조회 | 부분 구현 | 컴포넌트 useState/useEffect + 공통 apiFetch. 외부 상태 라이브러리·전역 서버 캐시 없음. 휴가 화면은 AbortController/ref guard, 계정 focus 재확인 있음. 목록·상세의 이전 응답 방어는 부족 |
| API 오류 계약 | 구현됐지만 추가 검증 필요 | HttpOnly cookie + credentials/include, ApiError와 request ID. 일부 도메인 오류 한글화. FastAPI 422 기본 형식은 error envelope와 달라 필드 오류가 일반 메시지로 축약될 수 있음. 공통 timeout 없음 |
| API 계층 | 구현 및 검증 완료 | route는 인증/dependency/schema/응답 변환, `services/approval.py`, attendance, Agent 서비스가 업무 규칙 담당. 모든 route가 async일 필요는 없으며 현재 동기 DB/SDK 경계에 맞음 |
| 결재 권한/상태 | 구현 및 검증 완료 | author/assigned approver, command endpoint, version 검사, 재상신 round 보존, inactive 차단. 기존 회귀 테스트 통과. 진짜 PostgreSQL 동시 실행 검증은 별도 |
| DB 스키마 | 구현됐지만 추가 검증 필요 | 7개 전진 migration, FK·unique·leave 합계 check, confirmation unique, account version, 승인 row lock 존재. SQLite migration head와 seed 실행 성공. PostgreSQL migration은 이번에 미실행 |
| 인덱스 | 부분 구현 | author/status/approver 등 단일 인덱스, `(approval_id, round, step)` unique, 직원/연도 leave unique, pgvector HNSW 이미 있음. 목록 정렬 복합 인덱스·실제 EXPLAIN 근거 없음 |
| LLM 경계 | 구현 및 검증 완료 | adapter 교체, Pydantic Structured Output, read Tool allowlist, actor scope, 최대 round/call, timeout/retry, fake provider 회귀 테스트. 실제 모델 품질은 이번에 미검증 |
| AI 쓰기 | 구현 및 검증 완료 | preview hash·actor·만료·snapshot 서명 → 명시적 Draft 확인 → 별도 제출 확인. replay·stale·tampering 테스트 통과. 기존 서비스를 새로 만들지 않음 |
| 인증 | 부분 구현 | Argon2/PyJWT/HttpOnly, secure 설정 fail-fast. 고정 demo 계정·공통 비밀번호·기본 입력은 로컬 전용. 계정 수명주기/세션 강제 폐기/SSO 없음 |
| CSRF/CORS | 구현 및 검증 완료 | 이번에 안전하지 않은 method에 고정 frontend Origin/Referer 검증 추가. production 무헤더 거부, 개발 무헤더 허용. CORS 단일 origin 유지. TLS/proxy 배포에서의 검증은 대기 |
| XSS/브라우저 보안 | 구현됐지만 추가 검증 필요 | React 텍스트 렌더링 사용. 저장형 입력·AI 출력에 대한 브라우저 공격 시나리오와 CSP/보안 header 검증은 없음. CSRF 검사는 XSS 방어가 아님 |
| 민감정보 | 부분 구현 | 설정 SecretStr, provider store=False, 예외 로그에서 vendor message 제거. workflow DB에는 request/answers/preview JSON이 저장되므로 로그 최소화와 DB 보존 정책은 별개. 보존 기간·정리 작업 없음 |
| Multi-service/K8s/Kafka | 현재 규모에서는 불필요 | 단일 서비스 경계와 transaction을 보존하는 편이 단순함. 필요성을 입증한 부하/운영 요구 없음 |

## UI/UX 진단

실제 브라우저는 Playwright의 Next dev + 격리된 임시 SQLite API + fake LLM/embedding으로 실행했다.
desktop/mobile Chromium emulation 8개가 통과했고 새 [스크린샷](screenshots/2026-10-21/)을 저장했다.
mobile 후보 화면과 desktop preview 이미지를 육안 확인했다. 전체 화면 수동 탐색이나 실기기·보조공학 검증은 아니다.
이번은 UI 변경이 없어 Before/After 개선을 주장하지 않는다.

| 화면/상태 | 분류 | 사용자 목적, 관찰과 개선 필요 |
| --- | --- | --- |
| 로그인/최초 진입 | 부분 구현 | 가상 계정 선택→로그인→결재 목록. 공개 계정/비밀번호가 기본 입력됨. 입력 autocomplete/required, 오류 alert·필드 연결 보완 필요. 공개 운영용 로그인 모드는 별도 필요 |
| 홈/대시보드 | 미구현 | `/`는 목록 redirect. 대기 결재·잔여 연차·최근 활동을 묶는 대시보드는 없음 |
| 결재 목록 | 부분 구현 | 내 문서/결재할 문서 구분, 로딩·빈 화면·오류 있음. 모든 문서 카드 렌더링, 검색/정렬/필터/페이지 이동 없음. scope 전환 시 오래된 응답이 새 화면을 덮을 수 있음. role=tab에 방향키/tabpanel 연결 불충분 |
| 결재 상세·승인 | 구현됐지만 추가 검증 필요 | status/version/이력/반려 사유·window.confirm 있음. 오류 뒤 명확한 새로 읽기·재시도 경로와 상세 조회 취소 보완. 브라우저 E2E는 휴가 Draft 상세까지이며 관리자 승인 전체 흐름은 API 테스트 중심 |
| 작성·편집 | 구현됐지만 추가 검증 필요 | 일반/출장/휴가 필드, 합계 계산, 저장 상태·오류. 장문 입력·모바일 폼·422 field focus·연속 저장/뒤로가기 시 복구 검증 필요 |
| 근태·휴가 | 구현 및 검증 완료 | 가용/사용/대기 연차, 공용/팀 일정, 후보와 제외 근거, 수동 fallback. 입력 변경 시 이전 결과 제거, 진행 중 중복 작업 제한·계정 전환 초기화 E2E 통과. 출퇴근 체크인/관리자 근태 관리 기능과는 다름 |
| AI 휴가 Agent | 구현 및 검증 완료 | 질문→후보→preview→명시적 Draft 저장, provider 오류 수동 복구·키보드 Enter 경로 검증. 별도 submit Agent와 일반 업무 Tool UI는 더 넓은 브라우저 테스트 필요 |
| 조직/사용자 관리 | 부분 구현 | employees/me와 active departments 조회, 프로필/직속 관리자 정보 있음. 직원/조직 CRUD 관리 화면은 없음. README의 조직 조회와 관리 제품 기능을 구분 |
| 디자인 시스템 | 부분 구현 | globals.css의 색상/radius/shadow 토큰과 버튼/카드, StatusBadge, AppShell 존재. spacing/typography/상태 컴포넌트 규격과 격리 예시 없음. CSS 한 파일에 화면별 규칙 누적 |
| 반응형 | 구현됐지만 추가 검증 필요 | 900/640px breakpoint, 후보/preview의 mobile 폭·줄바꿈 E2E 및 이미지 확인. 전체 테이블·긴 제목·오류·200% 확대·실제 휴대폰 검증 대기 |
| 접근성 | 부분 구현 | label·semantic HTML·focus-visible·일부 role alert/status, 키보드 주요 흐름 있음. WCAG 2.2 AA 인증/충족을 주장할 수 없음. axe 자동 감사 및 키보드/스크린리더/대비 수동 결과 없음 |

## 운영·품질 진단

| 대상 | 분류 | 실제 구현과 남은 검증 |
| --- | --- | --- |
| Docker build | 구현됐지만 추가 검증 필요 | API python:3.12-slim + uv frozen, web node:24-alpine standalone multi-stage, SWC helper 보완. base image digest·uv 설치 버전 고정/비root 실행 미완성 |
| Compose release | 구현됐지만 추가 검증 필요 | DB healthy→migrate 성공→synthetic seed 성공→API ready→web. config 구문 통과. `5432:5432`, `8000:8000`, `3000:3000` host port, 개발 cookie/origin 고정이므로 production 파일로 사용 불가 |
| CI | 구현됐지만 추가 검증 필요 | validate, browser, container-smoke, PR dependency-review 설정 존재. 이번에 동일 검사 일부 로컬 실행. GitHub의 최신 실행/필수 검사 설정은 조회하지 않음 |
| 실제 CD | 미구현 | registry push·commit digest release record·staging/prod 배포 workflow·GitHub Environment 승인·traffic switch 자동화 없음. runbook의 목표 계약과 구분 |
| HTTPS/공개 URL | 미구현 | 외부 endpoint/도메인/TLS/secret manager 배포 증거 없음. 설정 fail-fast와 외부 배포 완료는 다름 |
| 백업/복원 | 부분 구현 | runbook의 snapshot/복구 원칙 있음. 자동 pg_dump/보존/암호화/오프사이트 저장·clean DB 복원 시험·RPO/RTO 측정 없음 |
| Health/Readiness | 구현 및 검증 완료 | live와 DB SELECT 1 ready, DB 실패 503/내부 정보 숨김 테스트. migration revision 일치·pool exhaustion·provider readiness를 보장하는 검사는 아님 |
| 로그 | 구현 및 검증 완료 | JSON/ContextVar request ID, 제한된 외부 ID, latency, 오류 코드. 예외 vendor message 비노출 회귀 테스트. 원문 대화 미로깅은 DB 저장과 구분 |
| 모니터링/오류 추적 | 미구현 | 외부 uptime 알림·metric 집계·frontend error tracking·SLO/보존/경보 체계 없음. OTEL 전체 수집은 우선순위 낮음 |
| 장애 실험 | 부분 구현 | fake provider 실패·DB ready 실패·submit 응답 유실 재조정 테스트 있음. 실제 DB 중단/네트워크 timeout/복구와 배포 실패 drill 없음 |
| 종속성 보안 | 부분 구현 | 현재 JS production audit 알려진 취약점 0. PR dependency-review는 변경분 검사. Python 전체 감사·전체 dev 감사·image scan/secret scan은 미검증 |
| Rate limit/AI 비용 | 미구현 | provider timeout/retry/출력 token·Tool 횟수 제한 있음. 로그인/IP/actor 요청량 제한, 일일 token 예산, 동시 provider 호출 제한은 없음. 공개 데모는 AI key 없이 시작하도록 제안 |
| 성능 시험 | 미구현 | k6/Locust, 규모별 seed, EXPLAIN·query count·API percentile·CWV·Profiler 기록 없음. 단위/E2E 실행 시간을 성능 수치로 대체하지 않음 |

## 코드에서 확인한 대량 데이터 위험

다음은 정적 분석에 근거한 병목 후보이며 성능 측정 결과가 아니다.

1. `services/approval.py:list_approvals`가 limit 없이 updated_at만으로 정렬한다. API는 전체
   `ApprovalRead`(본문·details·attachments·모든 결재선)를 serialize하고 `total=len(items)`로 반환한다.
   author joinedload와 lines selectinload는 이미 있으므로 무조건 N+1이라고 주장하지 않는다.
   조회량/본문 크기/결재 회차가 늘수록 DB·Python 메모리·전송·DOM 비용이 함께 증가한다.
2. `enterprise_tools.py:_approvals`의 limit 10은 DB limit이 아니다. 모든 내 결재를 읽고 Python에서
   상태 필터 후 slice한다. UI pagination과 함께 Tool 조회/total 계약도 SQL로 옮겨야 한다.
3. 정렬 tie-break ID가 없어 동률 순서가 불안정하다. `(updated_at, id)` cursor도 수정 중 정렬 이동에는
   snapshot을 보장하지 않는다. 안정적 created_at 정렬 또는 refresh/snapshot 계약을 결정한 뒤 구현한다.
4. author+정렬, approver+approval 후보 복합 인덱스는 EXPLAIN으로 검증해야 한다. 무조건 추가하지 않는다.
   assigned JOIN/DISTINCT의 비용은 EXISTS 대안과 비교한다. lightweight summary DTO를 상세 DTO와 구분한다.
5. `mappers.py`에서 접근하는 관계는 실제 SQL 계측으로 확인해야 한다. 기존 eager load만 보고 전체 경로
   N+1 부재를 단정할 수 없다. query count 테스트와 행 수 변화에 따른 실행 계획이 필요하다.
6. 휴가 탐색은 최대 93일/후보 limit이 이미 있다. 다만 기간 내 이벤트를 매 날짜마다 검사하므로 팀 이벤트가
   많으면 비용이 증가한다. 이벤트 수·분포를 늘려 측정한 후 날짜별 사전 인덱싱을 비교한다.
7. pgvector HNSW는 이미 migration에 있다. SQLite cosine fallback 성능을 production vector 성능으로
   해석하지 않는다. policy 최신 버전·유효일 필터와 실제 index 사용 여부를 PostgreSQL에서 확인한다.
8. `pool_pre_ping=True`는 끊어진 연결 확인이며 pool 크기/대기 timeout/DB max connection 예산 수립과 다르다.
   row lock·계정 version은 존재하지만 SQLite가 PostgreSQL lock/isolation을 재현하지 못한다.
9. FE 목록은 map 전체 렌더링과 미취소 fetch다. 먼저 서버 조회량을 제한하고 trace/Profiler를 수집한다.
   이후에만 virtualization/useTransition/Worker 도입을 판단한다. 현재 모든 기술을 동시에 넣을 근거는 없다.

## 우선순위별 문제

P0=공개 배포 차단, P1=다음 개선, P2=후속 품질 개선. 난도는 상대적이며 일정 보장이 아니다.

| ID | 심각도 | 문제/사용자 영향 | 난도·예상 작업 범위 | 의존성/완료 근거 |
| --- | --- | --- | --- | --- |
| SEC-01 | P0 | 고정 demo 계정/패스워드로 공용 데이터 수정 가능 | 중·인증/UI/seed/공개 모드 2~3 단위 | 데모 세션 격리 또는 제한된 계정 정책·만료/리셋·브라우저 검증 |
| SEC-02 | P0 → 로컬 해결 | Cookie 쓰기 출처 검사 없음 | 소·API 경계+회귀 1단위, 이번 구현 | 39개 신규 테스트. staging TLS/proxy 검증 대기 |
| SEC-03 | P0 | 로그인/API/AI 호출 남용과 비용 급증 | 중·로그인/업무/AI budget 별도 2~3 단위 | proxy/worker 수 선택, 429/Retry-After·한계·복구·provider 미호출 증명 |
| OPS-01 | P0 | 개발 Compose의 외부 DB port·개발 설정 | 중·production topology/TLS/secret/nonroot 2단위 | 인프라 승인 후 외부 5432 차단·secure cookie 검증 |
| OPS-02 | P0 | 복원 미검증으로 장애 시 데이터 손실 | 중·backup+restore drill 2단위 | 합성 PostgreSQL, 보존/RPO/RTO·복원 무결성 기록 |
| OPS-03 | P1 | 수동 문서뿐인 CD·실패 복구 불확실 | 중~상·image/staging/prod 3단위 | registry·환경 권한, OPS-01/02, 승인 gate |
| PERF-01 | P1 | 전체 결재/이력 반환 및 DOM 증가 | 중·baseline→SQL/DTO→UI 3단위 | 합성 seed, summary 계약, Tool 호출 영향, 동일 조건 재측정 |
| FE-01 | P1 | 목록 scope 경합으로 다른 탭 결과 표시 | 소·취소/최신 요청 방어+E2E 1단위 | 지연 응답 역전 재현, loading/error/retry UX |
| DATA-01 | P1 | PostgreSQL 동시 변경 결과 미검증 | 중·실제 DB 통합 테스트 1~2단위 | Docker 또는 별도 DB; 승인/예약/멱등성/rollback invariant |
| QA-01 | P1 | Windows cp949에서 기존 평가 JSON 테스트 5개 실패 | 소·명시적 UTF-8 I/O 별도 수정 1단위 | 현재 `python -X utf8`로 실행 가능. platform 기본값에 의존하지 않는 회귀 추가 |
| UX-01 | P2 | 상태 UI·폼 feedback·키보드 규격 불일치 | 중·목록 대표 화면→공통 컴포넌트 단계별 | Phase 2 대표 화면 검토·AA 자동/수동 결과 |
| OBS-01 | P1 | 배포 후 지연/오류/장애 감지 수단 없음 | 중·metric/uptime/FE 추적 2단위 | 최소 수집/비식별 설정, 장애 주입·복구 기록 |
| GOV-01 | P2 | workflow 원문/preview 보존 기간 없음 | 중·보존/정리/데모 리셋 1~2단위 | synthetic/운영 환경 분리, 삭제 dry-run·권한·backup 정책 |

## 이번 실행 결과와 재현

환경: Windows, Python 3.12(기존 시스템), 별도 `.venv`, Node 24.19.0(번들), pnpm 10.30.3,
uv 0.11.24. 시스템 기본 Node 20.11.1은 사용하지 않았다. 의존성은 frozen lockfile로 설치했다.
일부 TestClient/패키지 설치가 sandbox 제한으로 진행되지 않아 승인된 일반 로컬 실행으로 검증했다.
기존 개발 DB/비밀 설정은 사용하거나 변경하지 않았다. 실제 모델 평가·유료 호출은 실행하지 않았다.

API 디렉터리에서 root `.venv`의 실행 파일을 사용했다. 일반적인 재현 명령은 다음과 같다.

```powershell
# root에서 설치
uv sync --frozen --project apps/api
pnpm install --frozen-lockfile
# Windows에서 기존 JSON 인코딩 문제를 우회해 기준 검사
$env:PYTHONUTF8 = '1'
pnpm validate
pnpm exec playwright install chromium
pnpm test:e2e
pnpm audit --prod
```

| 실행/검증 범위 | 실제 결과 |
| --- | --- |
| 변경 전 API lint / strict mypy | 통과, mypy 99 files |
| 기존 API 기준: `python -X utf8 -m pytest --ignore=tests/test_csrf.py` | 111 passed, 14.89s |
| 기본 Windows 인코딩 | 기존 평가 dataset 5개 UnicodeDecodeError(cp949). UTF-8 모드 결과와 구분 |
| 보안 수정 전 재현 | 신뢰하지 않는 Origin 로그인 200+cookie, 결재 생성 201. 신규 기대값 403 테스트 실패 확인 |
| 수정 후 API lint / strict mypy | 통과, mypy 101 files |
| 최종 `python -X utf8 -m pytest --junitxml=../../docs/engineering/evidence/api-2026-10-21.xml` | 150 passed, 14.67s(기존 111 + 신규 39). [JUnit 결과](evidence/api-2026-10-21.xml) |
| Web lint / TypeScript / Next production build | 모두 통과(각 package script 실행), Next 16.3.8 |
| 변경 후 `pnpm test:e2e`, UTF-8 환경 | 8 passed, 31.0s. desktop/mobile 각 4개, 실제 HTTP+임시 DB+fake AI |
| `pnpm audit --prod` | 알려진 JS 운영 종속성 취약점 0. Python/dev/image 감사 결과와 구분 |
| `docker compose config --quiet` | 구문 검사 통과 |
| Docker engine | ServerVersion 조회 실패. 엔진 실행 불가 상태로 container smoke/PostgreSQL 테스트 미실행 |
| Alembic fresh SQLite + synthetic seed | `.venv/assessment-migration.db`만 생성, 7개 revision 적용, head `b63d91e52fa0`, seed 성공 |
| `git diff --check` | 통과 |

이번 실제 구현은 `core/csrf.py`, `main.py`의 쓰기 출처 guard와 회귀 테스트다.
출처 검사는 서비스 실행 전에 거부하고 request ID/안전한 error/log 계약을 유지한다.
신뢰 frontend의 정상 로그인/preflight, Referer fallback, production 무헤더 거부, 개발 CLI 호환,
거부 후 DB/세션 무변경을 검사한다. 보안의 원리·대안·실습은 [작업 기록](csrf-origin-guard.md)에 있다.
수정 전 재현은 TestClient가 쿠키와 외부 Origin을 직접 보내 서버 경계의 검사 부재를 확인한 것이다.
현재 JSON 요청·custom header preflight·SameSite가 적용된 실제 브라우저에서 공격이 성공했다는 증거는 아니다.
이번 변경은 이 기존 방어에 서버의 명시적 출처 검증을 더한 것이다.

이 문서·[로드맵](roadmap.md)·인프라 비교는 계획/분석이며 해당 기능이 구현됐다는 증거가 아니다.
공개 배포/registry push/결제/production migration/데이터 삭제는 수행하지 않았다.

## 다음 세션 시작점

최종 검사 결과와 `git diff --check`, working tree를 확인한다. QA-01의 인코딩 문제를 별도 작은 변경으로
해결한 뒤 SEC-01/03과 로컬 PostgreSQL 검증을 진행한다. 공개 서비스는 P0 gate를 충족한 후에만 승인 요청한다.
대용량 작업은 PERF-01 baseline부터 시작하며 성능 개선율은 아직 없다.
