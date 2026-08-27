# Phase 11 — Evaluation, Guardrail, Observability, Deployment, Portfolio

상태: **진행 중 — Checkpoint 16 완료 (2026-08-27)**

## 1. Checkpoint 16 목표

기능 시연과 운영 준비를 분리한다. 외부 모델 품질은 비용이 발생하는 명시적 평가 작업에서 측정하고,
일반 CI는 결정적 테스트·정적 검사·production build·container build를 재현한다. 배포된 API는 요청 하나를
안전한 correlation ID로 추적하고, process 생존과 DB 준비 상태를 분리해 알린다.

## 2. 통합 AI 평가 게이트

```bash
pnpm eval:all
```

위 명령은 승인 검토, 자연어 Draft, 업무 조회 Tool, 정책 검색, 휴가 상담의 기존 실제 모델 평가를 각각
별도 process로 실행한다. `apps/api/evals/suite.json`의 capability별 최소 통과율과 필수 safety case를 적용하고 다음을 하나의
`artifacts/evals/latest.json`에 기록한다.

- capability와 case 통과 수, 필수 safety case 실패, 실행 불가·잘못된 report 상태
- capability별 실행 시간, case p95 모델 latency와 token 합계
- provider/model, tool·citation·구조화 결과를 포함한 기존 평가 report

API key나 provider가 없어 실행하지 못한 경우 exit code `2`, 품질 기준 미달이나 잘못된 report는 `1`,
모든 기준을 만족하면 `0`이다. report와 로그에는 평가 요청 원문이나 API key를 복제하지 않는다. 데이터셋은
JHWorks synthetic data이며 애플리케이션 쓰기 Tool을 호출하지 않는다.

외부 모델 평가는 비결정성과 비용 때문에 일반 PR CI에서 자동 실행하지 않는다. 모델, prompt, embedding,
retrieval 설정을 변경한 PR은 작성자가 `pnpm eval:all` 결과를 실행 증거로 첨부한다.

## 3. API 운영 경계

| 항목 | 계약 |
| --- | --- |
| Liveness | `GET /api/v1/health/live`, process가 요청을 처리하면 `200` |
| Readiness | `GET /api/v1/health/ready`, DB `SELECT 1`까지 성공해야 `200` |
| Correlation | web이 `X-Request-ID`를 생성하고 API 응답 header와 오류 body가 같은 ID를 반환 |
| 입력 제한 | 외부 request ID는 128자 이하의 영문·숫자·`._:-`만 허용, 나머지는 UUID로 교체 |
| 로그 | 기본 JSON, UTC 시각·level·logger·requestId·event·상태·latency 포함 |
| 예외 | 예상하지 못한 오류는 내부 상세를 응답하지 않고 안정적인 `INTERNAL_SERVER_ERROR`로 변환 |

request context는 Python `ContextVar`로 전달되므로 같은 요청 안의 AI adapter, RAG, Tool과 상태 머신 로그에도
별도 actor ID 복제 없이 request ID가 붙는다. query string, cookie, token, prompt 원문은 access log에 남기지 않는다.
예외 로그는 type과 실행 frame만 남기고 vendor·DB 오류 message를 복제하지 않는다. AI 검토 수정안에 source의
prompt-like 명령이 남으면 adapter가 해당 문장을 결정적으로 제거하며, 원문 Approval은 변경하지 않는다.

## 4. Production 설정 가드레일

`JHWORKS_ENVIRONMENT=production`에서는 API가 다음 오설정을 startup에서 거절한다.

- 32자 미만 또는 local 기본 JWT secret
- secure cookie 비활성화
- PostgreSQL이 아닌 database URL
- HTTPS origin이 아니거나 path를 포함한 frontend origin

OpenAI API key는 선택 사항이다. 키가 없으면 핵심 그룹웨어와 결정적 휴가 기능은 계속 동작하고 각 AI endpoint만
기존의 안전한 `503`을 반환한다.

## 5. CI와 배포 준비

GitHub Actions는 Python 3.12, Node.js 24, pnpm 10 lockfile 환경에서 `pnpm validate`를 실행하고 API/web Docker
image를 각각 build한다. PR에서는 high severity dependency change도 차단한다. 외부 API key와 application secret은
CI에 주입하지 않는다.

실제 배포 플랫폼과 public URL은 이 체크포인트에 포함하지 않는다. 플랫폼 선택 후에는 managed PostgreSQL/pgvector,
TLS, secret manager, migration 단일 실행, backup/restore, CORS origin, cookie domain을 플랫폼 설정으로 검증한다.

검증 결과는 backend 102 tests, frontend lint/type-check/production build, API/web container build를 통과했다.
실제 `gpt-5.4-mini-2026-03-17`과 `text-embedding-3-small` 통합 평가는 5/5 capability, 29/29 case와 모든
필수 safety case를 통과했으며 report의 총 사용량은 25,028 tokens였다.

## 6. 다음 체크포인트

Checkpoint 17은 배포 대상에 맞춘 release/rollback runbook, 실제 smoke test와 portfolio용 architecture·위험 통제
증거를 완성한다. 모델 변경이 있으면 통합 평가 baseline도 함께 갱신한다.
