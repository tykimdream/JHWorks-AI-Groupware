# 엔터프라이즈 고도화 로드맵

작성 기준: 2026-10-21, 로컬 `9814045`. 기존 제품 Phase 1~11을 다시 구현하는 계획이 아니다.
현재 증거는 [assessment](assessment.md), 첫 구현의 판단은 [CSRF 작업 기록](csrf-origin-guard.md)에 둔다.
한 작업은 문제/완료 조건→대안→구현→관련 검사→결과/위험 기록 순서로 진행한다.
진단/계획과 CSRF 구현은 별도 커밋으로 나누어 하나의 초기 고도화 PR에서 검토한다.

## 진행 상태

- [x] Phase 0: Git/지침/구현/테스트/CI/UI/DB 정밀 진단, 기준 테스트·build 재검증
- [x] 첫 구현: Cookie 쓰기 출처 검증과 기존 업무 흐름 회귀 테스트
- [ ] Windows JSON 읽기 인코딩을 명시적으로 수정(QA-01, 현재 UTF-8 실행 우회)
- [ ] 공개 데모 인증 격리·API/AI 호출량 제한
- [ ] 실제 PostgreSQL 검증 및 승인받은 인프라 staging 배포
- [x] Supabase online migration과 Cloud Run private 기동·별도 수동 smoke 4개 검증
- [ ] CI URL 별칭 수정 반영·정상 release 재검증·backup/restore 및 실제 업무 검증
- [ ] 목록 대표 UI/디자인 시스템, 규모별 성능, 장애 복구와 포트폴리오 증거

## 우선순위 조정 — 먼저 배포하고 지속 개선

2026-10-21 사용자 피드백으로 다음 마일스톤을 **외부에서 접속 가능한 제한 공개 staging과 CD**로 앞당긴다.
디자인/대용량 성능/전체 운영 고도화가 완료될 때까지 첫 배포를 미루지 않는다.
QA-01은 작은 독립 수정으로 처리하되 전체 배포 준비를 뒤로 미루는 선행 단계로 삼지 않는다.

1. 첫 배포 PR: Cloud Run web ingress + FastAPI sidecar, 동일 출처 `/api/v1` proxy,
   Supabase Free의 비공개 업무 schema와 분리된 DB role,
   secure cookie/origin/secret 주입, 합성 데이터의 명시적 초기화 절차를 준비한다.
   staging은 별도 접근 제한으로 보호하고 유료 AI key는 주입하지 않는다.
   현재 공개 demo 계정만으로 인터넷의 누구나 쓰기 가능한 서비스는 열지 않는다.
2. CD PR: 기존 CI 통과 후 SHA/digest 이미지 생성 → staging migration 단일 실행 → rollout →
   readiness/smoke → 실패 시 직전 application digest 복귀를 구성한다.
   기존 DB는 배포마다 seed/reset하지 않는다. migration 호환성·backup/restore 확인을 배포 조건으로 둔다.
   GitHub Environment의 production 승인 단계는 유지한다.
3. 인프라·domain·secret 접근을 확보한 뒤 제한 공개 staging의 실제 로그인/저장/TLS/CSRF를 검증한다.
   이후 작은 PR을 main에 병합하면 검증된 버전이 staging에 반영되도록 운영한다.
4. 익명 방문자도 사용할 공개 demo는 인증/데이터 격리·호출 제한·비용 제한·취약점 분류를 완료한 뒤 연다.
   UI/성능 개선은 배포된 staging에서 전후를 측정하며 계속한다.

사용자와 비교 후 **Cloud Run + Supabase Free** 방향을 선택했다. 단일 VPS는 대안 기록으로 남긴다.
초기 cloud 예산은 월 1만원 목표이며 hard cap이 아니다. AI 월 $5는 별도 제안이며 실제 provider 예산과
서버 제한을 구현하기 전에는 연결하지 않는다. 부하 실험은 로컬 PostgreSQL + fake AI로 한정한다.
로그인된 앱 안 브라우저에서 기존 결제 연결 프로젝트를 읽기 확인했으며 그룹웨어 전용 project는 없었다.
전용 GCP 프로젝트 `jhworks-staging-tykimdream`과 사용자 생성 Supabase Free 서울 프로젝트는 준비됐다.
GCP registry·실행 계정·Secret version 1·한정된 IAM/WIF 설정과 2026-10-21 첫 private 배포를 수행했다.
비밀 값은 저장소/채팅에 기록하지 않는다. 익명 포트폴리오 방문자용 공개일은 아직 정하지 않았다.

이번 구현의 범위와 검증은 [Cloud Run 첫 단위](cloud-run-supabase-plan.md),
외부 설정 순서는 [배포 가이드](../operations/cloud-run-supabase.md)를 따른다.
현재 CD는 exact main CI를 요구하는 수동 승인형 workflow다. 사용자 승인 후 전용 저장소에서 활성화했다.
main 자동 배포는 백업 자동화와 실제 staging 검증 뒤 별도 단위로 추가한다.
로컬 구현은 TLS/실패 진단 수정 후 API 183개, 브라우저 10개, lint/type/build를 통과했다.
[배포 준비 검증 기록](cloud-run-supabase-verification.md)에 외부 미검증 범위와 재개 순서를 남겼다.
Supabase 전용 프로젝트 생성은 사용자가 완료했다. 서울·Healthy·Data API 비활성을 확인했고 사용자 승인으로
vector/schema/role bootstrap 및 읽기 권한 검증(all_checks_ok=true)을 완료했다.
이후 실제 앱 pooler 연결과 migration head `b63d91e52fa0`, 업무 테이블의 기본 권한을 확인했다.
GCP 전용 예산 알림·서울 immutable Docker 저장소·권한 없는 전용 계정 3개·빈 secret 보관함 3개를 생성했다.
사용자의 credential helper 실행과 Secret version 1 등록은 완료했고, 승인된 runtime/migrate Secret 읽기
권한 4개도 버전 조건과 함께 연결했다. PR #18 병합과 main CI를 통과했고 WIF/배포 권한을 적용했다.
첫 release attempt 1의 immutable subject 불일치를 교정했으며 attempt 2에서 실제 GitHub→GCP 인증이 성공했다.
이미지 build/push도 통과했으나 첫 service 부재의 CLI 오류 문구 차이로 release가 중단됐다.
목록 JSON으로 존재 여부를 판단하도록 수정했고 API 190개/lint/strict mypy를 통과했다.
PR #19 병합 후 `dfff250`의 실제 migration/service Ready와 별도 수동 smoke 4개를 통과했다.
CI release는 정상 URL 별칭을 거부해 실패했다. 해당 비교와 서비스 전체 max=2를 수정해
API 197개/lint/strict mypy를 통과했다. 새 수정의 PR/CI 및 backup/restore 후 일반 release 검증이 남아 있다.
사용자가 요청한 승인 생략과 main 자동 배포 방법은 배포 가이드에 설명했으며 실제 설정은 바꾸지 않았다.
최신 증거와 재개 지점은
[첫 staging 배포 기록](staging-rehearsal.md)에 둔다. 공개 전환과 AI 연결은 별도 gate다.

## Phase별 작은 작업과 완료 조건

| 순서/작업 | 범위·선택 기준 | 완료 조건과 증거 | 선행 조건 |
| --- | --- | --- | --- |
| 0-A 진단 | 기존 코드와 historical 기록 구분 | assessment, 로컬 baseline, UI 이미지, 위험/난도/범위 | 완료 |
| 1-A 출처 검증 | 단일 frontend Cookie API의 Origin/Referer guard. token 체계 추가 대신 작은 경계 선택 | 변조/누락/중복/다른 port 거부, DB 무변경, 정상 workflow 회귀 | 로컬 완료, staging 후속 |
| 1-B 개발 재현성 | locale 기본 인코딩 의존 제거 | Windows 기본 모드/Linux에서 평가 dataset 읽기 및 전체 테스트 | 비용/외부 인증 불필요, 다음 작업 |
| 1-C 공개 데모 정책 | local demo 로그인과 public 모드 분리, 합성 데이터만 사용. 가능하면 session별 격리/만료, shared demo는 쓰기 제한 | 기본 공개 비밀번호 미허용, 타 세션 데이터 접근 차단, seed 환경 guard, reset dry-run과 보존 정책 | SEC-01/GOV-01 |
| 1-D 남용/비용 제한 | 로그인·일반 API·AI의 서로 다른 예산. 단일 instance는 proxy+최소 상태부터, worker가 늘면 공유 원자 카운터 비교 | 429/Retry-After, 동시 요청 경계, TTL 회복, AI budget 초과 시 provider 호출 0회. 기본 AI key 미주입 | 배포 topology·신뢰 proxy 결정 |
| 1-E production artifact | 기존 Docker 재사용, 비root/버전 고정·DB 비노출·HTTPS proxy/secret 주입. 로컬 Compose와 분리 | image scan, config fail-fast, 5432 외부 차단, Cookie/CORS/CSRF 실제 browser 확인 | Docker engine, 1-C/D |
| 1-F 백업/복원 | synthetic PostgreSQL에 pg_dump→별도 DB restore, schema/invariant 검증 | backup ID/보존/RPO 목표·실측 RTO, 예약/결재선/캘린더 검증, 기존 volume 비삭제 | 로컬 PostgreSQL |
| 1-G staging CD | 기존 4개 CI job 유지. 승인된 registry에 SHA tag+digest, release record, 단일 migration job | build→scan→staging migration→ready→smoke→E2E, migration 실패 시 rollout 없음 | 환경 권한·1-E/F, 인프라 승인 |
| 1-H production CD | GitHub Environment 수동 승인과 최소 배포 권한, 직전 digest 복귀 | release runbook을 실제 명령에 맞게 갱신, 실패 drill/rollback 후 동일 smoke 통과 | staging 증거·사용자 production 승인 |
| 2-A 대표 화면 | 결재 목록의 정보 밀도/상태/키보드/모바일 방향을 먼저 구현. 기존 CSS token 확장부터 | Before/After 동일 데이터·viewport 이미지, loading/error/empty/retry, keyboard/zoom 수동 확인 | 디자인 방향 1개 화면 검토 |
| 2-B 공통 규격 | 색·글자·간격·상태 token, Button/Field/Alert/EmptyState 등 반복 경계 | 격리 예시·필요한 동작 테스트, 대비/포커스 확인. 라이브러리 추가 시 비용/호환/번들 비교 | 2-A |
| 2-C 업무 화면 적용 | 로그인/대시보드→목록·상세→작성·승인→근태·AI→조직, 한 화면씩 | 사용자 목적/클릭/입력실수/복구 점검, axe 자동 결과와 WCAG 2.2 AA 수동 결과 분리 | 2-B, 서버 권한 유지 |
| 3-A 성능 baseline | 기존 도메인의 1k→10k→100k synthetic generator, seed 고정/분포·DB 크기 기록 | query count, 응답 byte, EXPLAIN ANALYZE BUFFERS, API p50/p95/p99·오류율·CPU/RSS/pool, React trace | 격리 PostgreSQL, 아래 실험 계약 |
| 3-B 서버 조회 제한 | 목록 summary DTO, 페이지 크기 상한, SQL 필터/정렬·Tool query도 제한. offset/cursor 비교 | 권한 필터 후 pagination, tie/경계/삽입·수정 중 중복·누락 계약, query count 테스트와 동일 부하 재측정 | 3-A·API/FE/Tool 계약 설계 |
| 3-C FE 경합·렌더링 | 요청 취소/최신 응답, loading/retry, cache 무효화. Profiler로 기술 선택 | 지연 응답 역전 E2E, mutation 뒤 최신 목록, bounded DOM, render/commit trace 비교 | 3-B, FE-01은 먼저 독립 수정 가능 |
| 3-D 동시성 | PostgreSQL 별도 connection/transaction에서 승인·수정·동일 token·같은 연차 경합 | 한 번 예약/한 번 결재선, 음수 연차 없음, conflict 명시, deadlock/timeout 후 rollback 검증 | 기존 lock/version/unique 재사용 |
| 3-E 1M DB 실험 | 브라우저로 전체 전송 금지, 100k 실측으로 저장공간/WAL/index/백업 비용 계산 | 여유 disk/RAM 확인 후 별도 실행 승인, 실행시간·query plan·정리 계획. 100k 완료로 1M을 주장하지 않음 | 3-A/D, 자원 검토 |
| 4-A 최소 관측 | 기존 JSON log/request ID 재사용. latency/error 집계·uptime·frontend exception부터 | 수집 항목/PII/보존/비용, 오류→request ID→원인 조회 가능, 알림 drill | staging |
| 4-B 장애 주입 | DB 중단·느린 API·provider timeout/429·응답 유실·배포 실패 | 실패 화면/안전한 재시도/복구·RPO/RTO 기록. write 무조건 자동 재시도 금지 | fake 테스트→실제 격리 DB 순서 |
| 4-C 추가 기술 판단 | OTel/분산 tracing·circuit breaker는 반복 장애/추적 공백 측정 후 | 도입/비도입 ADR, 동작·운영 가치 증거. 개인 규모에서 Kafka/K8s 등 기본 제외 | 4-A/B 측정 |
| 5-A 기술 증빙 | 기존 architecture-and-controls/runbook/ADR 재사용, 구현과 목표 분리 | 시스템/FE/API/AI/권한/배포/동시성/성능/복구 문서와 재현 명령 | 각 완료 단위마다 갱신 |
| 5-B 포트폴리오 | 웹/PDF에 재사용할 Markdown·이미지·CSV/JSON source | 서비스 URL(배포 후), synthetic 화면, 개선 전후 조건/실측/한계, 개인·회사 성과 분리 | 실제 증거 있는 항목만 |

## 배포 후보 비교와 비용 승인 경계

2026-10-21 공식 가격/문서를 확인했다. 아래는 소규모 개인 데모에 대한 설계 추정이며 견적/결제 승인이 아니다.
세금·환율·도메인·초과 전송·백업 저장·유료 AI는 별도다. 최종 선택 직전에 지역/재고/청구 화면을 재확인한다.

| 후보 | 월 비용/무료 범위 | 호환·운영·복구·확장성 |
| --- | --- | --- |
| Vercel Hobby + Render Free API + Neon Free PG | 무료 할당 내 $0. Vercel Hobby는 개인 비상업용. Render는 15분 idle sleep, Neon Free는 100 CU-hours/project/month·1GB/project 현재 표기 | Next 지원, FastAPI 장기 process와 pgvector 가능한 PG 분리. 관리 부담 낮지만 cold start/무료 제한·cross-site Cookie/지역 지연 점검 필요. TLS/secret은 각 플랫폼 설정, backup 보존은 plan별 확인과 별도 dump. 같은 site 도메인 또는 proxy 필요 |
| Vercel Hobby + Render 유료 API + Neon Free | API $7/month(512MB)부터, DB 한도 내 $0. 리소스 적합성은 측정 필요 | API cold start 회피. 관리형 운영으로 단순하지만 memory·DB usage·egress 비용이 별도. scale-out 시 DB pool/limit 공유가 필요 |
| 단일 VPS + Compose + TLS reverse proxy + 자체 PG/pgvector | Hetzner 유럽 CX23 예시 서버 €5.49/month(IPv4·VAT 제외), backup 서버 가격의 20% 추가. IPv4/도메인/오프사이트 저장 포함한 계획 예산 약 €8~12/month, 실제 총액 미확정 | 기존 이미지/SQL 호환 높음. same-origin `/api`로 Cookie 단순화. HTTPS 갱신·OS patch·secret 파일 권한·백업·복원을 직접 운영. 단일 장애점, 한국 latency 미측정. build는 CI에서 하고 DB 리소스는 실측 후 확장 |

무료 후보의 Render 자체 무료 PostgreSQL은 30일 만료이므로 장기 데모 DB 후보에서 제외했다.
Neon pgvector 지원이 있더라도 현재 HNSW extension version/권한과 migration 실행은 실제 환경에서 확인해야 한다.

공식 근거:
[Vercel Hobby](https://vercel.com/docs/plans/hobby),
[Render 무료 제한](https://render.com/docs/free),
[Render 가격](https://render.com/pricing?trk=article-ssr-frontend-pulse_little-text-block),
[Neon 가격](https://neon.com/pricing),
[Neon pgvector](https://neon.com/blog/sunset-pgembedding),
[Hetzner 2026-06 가격](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/),
[Hetzner backup 과금](https://docs.hetzner.com/cloud/billing/faq/).

**과거 비교 제안(현재 미선택):** 지속 접속 가능한 저비용 데모와 운영 실습을 함께 목표로 하면 단일 VPS를 검토했다.
운영 시간을 줄이고 싶으면 관리형 API+PG가 대안이다. 월 비용을 전혀 쓰지 않는 기간에는 무료 후보를
cold start 있는 비상업 데모로 제한하고, 안정적 상시 운영이라고 표현하지 않는다.

사용자 승인 요청은 보안 P0 보완과 로컬 검증 뒤에 한다. 그때 provider/지역·월 상한·backup·domain·AI 예산·
결제 수단 필요 여부·생성/삭제할 자원을 하나의 구체적 안으로 제시한다. 이번에는 계정 연결/자원 생성/결제 없음.
Production 배포·외부 push·기존 데이터 삭제는 별도 승인 대상이다.

## 성능 실험 계약

처음은 k6(HTTP percentile/threshold·CI artifact)를 후보로 두고, Python 서비스 내부 scenario 제어가 더 중요하면
Locust와 비교한다. 도구 선택만으로 성능이 개선되지는 않는다. 새로운 도구/라이브러리는 먼저 작은 재현에서 검증한다.

- dataset seed/행 수(문서·회차·팀 분포)/DB 크기, commit SHA, OS/CPU/RAM, PG 설정·pool·이미지 digest 기록.
- 동일 scenario에서 1/10/50 동시 사용자, warm-up 30초+측정 3분을 초기 계획으로 사용. 자원 포화/오류 시 안전 중단.
  데이터 규모·concurrency를 한꺼번에 바꾸지 않고 조회·승인/예약 쓰기 scenario를 구분한다.
- API p50/p95/p99·throughput·오류율, DB query count/time/plan·connection, 프로세스 CPU/RSS 수집.
- desktop/mobile 조건 고정, DOM 수·응답 크기·React render/commit·heap·LCP/INP/CLS를 분리 기록.
  lab 측정과 field CWV를 구분하며 Lighthouse 점수를 실제 사용자 성능으로 주장하지 않는다.
- 같은 dataset/환경/시간/측정 방법으로 baseline→변경→재측정. 캐시 warm/cold·반복 횟수와 편차 포함.
- 먼저 SQL/전송량을 제한한 뒤 DOM 병목에 virtualization, CPU 작업에 Worker, 입력 우선순위에 concurrent API를 검토.
  현재 어느 것의 성능 향상률도 측정하지 않았다.

## 재개·리뷰 절차

다음 세션은 assessment 결과와 이 체크리스트, `git status`부터 읽는다. 이번 PR은 CSRF 한 단위와
진단/계획/검증 artifact를 포함한다. 우선 QA-01을 별도 변경으로 처리하고 SEC-01/03으로 진행한다.
Cloud Run 첫 배포 브랜치의 검증을 확인하고 전용 외부 project/secret을 준비한다.
Docker 엔진이 준비되면 기존 container-smoke와 PostgreSQL 동시성부터 재현한다.
완료된 단위마다 구현 파일·실행 명령·실패/통과·외부 미검증·다음 작업을 갱신한다.
