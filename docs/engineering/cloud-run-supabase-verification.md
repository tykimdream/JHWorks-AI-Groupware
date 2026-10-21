# Cloud Run + Supabase 배포 준비 검증

2026-10-21, Windows, Python 3.12, Node 24, pnpm 10. 기준 main `ff035c0`, 작업 브랜치
`feat/cloud-run-supabase-release`. 아래 결과는 로컬 작업 트리 기준이며 클라우드 배포 증거가 아니다.

## 실제 구현

- Next.js의 선택적 same-origin API proxy. Cookie·Origin·request ID를 유지하고 기존 업무 API를 재사용한다.
- Web/API 비root 이미지 설정, 고정 digest·secret version·분리 service account를 요구하는 manifest 생성기.
- Supabase transaction pooler용 NullPool·prepared statement 비활성화 옵션과 migration 전용 DB 연결 분리.
- 명시적 AI 비활성화. key가 있어도 배포 설정의 `AI_ENABLED=false`이면 provider를 호출하지 않는다.
- migration 성공 후 rollout·인증 smoke·실패 시 이전 traffic 복구를 수행하는 release CLI.
- exact main CI 성공을 요구하는 수동 staging workflow. 기본 비활성이며 외부 실행하지 않았다.

## 실행 결과

| 검사 | 실행 방법 | 실제 결과 |
| --- | --- | --- |
| API lint | `ruff check app tests alembic` (apps/api) | 통과 |
| API 타입 | `mypy app tests` (프로젝트 strict 설정) | 106 source files 통과 |
| API 전체 | `python -X utf8 -m pytest --junitxml=../../artifacts/cloud-run/api-tests.xml` | TLS/실패 진단 수정 후 183 passed, 15.82초 |
| Web lint·타입 | `pnpm lint:web`, `pnpm type-check:web` | 통과 |
| Web production build | `/api/v1` + 내부 API proxy 설정으로 기존 build 명령 실행 | 통과, routes manifest의 내부 rewrite 확인 |
| 브라우저 전체 | `pnpm test:e2e` | desktop/mobile 합계 10 passed, 25.0초 |
| 배포 manifest | 예제 설정과 합성 digest로 CLI 실행 | service/job JSON 생성 성공, 클라우드 호출 없음 |
| workflow | YAML 파싱과 환경·동시 실행 설정 확인 | 파싱 통과, GitHub Actions 실행은 미검증 |

API 신규 테스트는 실제 클라우드 대신 fake command runner로 migration 실패 시 rollout 차단,
public IAM 거부, rollback traffic 분배·smoke, 최초 배포 명시 요구, 설정 오류와 AI 차단을 검증한다.
비밀 초기화 도구의 11개 테스트는 기존 배포/secret version이 있으면 차단, URL encoding·TLS 검증,
credential stdin 전달, 실패 시 진단 비노출, 로컬 SCRAM hashing 후 SQL 전송을 확인한다.
GCP preflight 실패 시 비밀번호를 묻지 않고, DB 오류 분류가 비밀 진단 문자열을 포함하지 않는지도 검증했다.
브라우저 신규 2개는 실제 로컬 Next proxy를 통해 잘못된 Origin 거부, 정상 로그인·HttpOnly cookie·
인증 조회·request ID를 확인한다. 기존 8개 업무 흐름도 동일 proxy를 통과했다.

## 발견한 제한과 미검증

- Windows 기본 cp949에서 기존 평가 JSON 읽기 문제가 남아 있다(QA-01). 전체 API 결과는 UTF-8 실행이다.
- Alembic 전체 head의 offline SQL 생성은 기존 `d92a5f6e10bc`의 JSON literal CompileError로 실패했다.
  과거 migration은 수정하지 않았다. URL의 percent escape 회귀 테스트는 앞선 `c7f3a91d42e8`까지
  offline SQL 생성을 확인한다. 이것으로 실제 PostgreSQL의 online head 성공을 주장하지 않는다.
- Docker 엔진 부재로 이번 이미지 build/container smoke를 로컬 실행하지 못했다.
- 실제 Supabase migration·TLS·앱 pooler 연결, GCP manifest 수용·WIF·IAM·
  identity token·bootstrap URL·rollout/rollback은 미검증이다. 아래 초기 DB SQL 검증과 구분한다.
- backup reference는 수동 증거 입력이다. 자동 백업·복원 drill·image scan·main 자동 CD는 후속 작업이다.
- 월 1만원은 목표 예산이다. max instance·concurrency와 예산 알림은 전체 청구액 hard cap이 아니다.
- 공개 방문자 데이터 격리·요청 제한·AI 공유 예산은 미구현이다. 첫 배포는 IAM private staging이며 AI는 꺼진다.

## 재개 순서와 완료 조건

1. 사용자가 Supabase 전용 Free 프로젝트를 생성했고 서울 리전을 확인했다. 최초 상태는 `Coming up...`으로
   연결 정보 조회와 online 검증은 준비 완료 후 진행한다. 비밀번호는 사용자가 직접 설정·보관했다.
2. GCP 전용 프로젝트 `jhworks-staging-tykimdream` 생성·콘솔 전환을 확인했다. 예상 유료 자원을
   구체화해 승인받은 뒤 registry·secret·최소 IAM/WIF를 설정한다.
   장기 service-account key 대신 GitHub OIDC를 사용한다.
3. 전용 합성 DB에서 online migration과 권한 음성 테스트, 백업→다른 DB 복원을 실행한다.
4. 이미지/기존 CI 검증 후 private staging 최초 배포, 인증 smoke와 실제 TLS·cookie·실패 복구를 기록한다.
5. 공개 gate를 별도 작은 PR로 구현·검증한 뒤 포트폴리오 방문자에게 공개한다. 부하 실험은 로컬에서만 한다.

## 실제 외부 초기 설정 결과

- 사용자 승인 후 GCP API 활성화, 서울 Docker registry `jhworks` 생성 및 immutableTags=true 확인.
- 전용 service account 3개와 Secret Manager 보관함 3개 생성. 초기에는 값/추가 IAM 없이 생성했으며
  이후 아래 사용자 실행과 승인으로 version 1 등록 및 네 개의 Secret별 읽기 binding을 완료했다. key는 발급하지 않았다.
- 프로젝트 한정 월 1만원 예산, 50%/100% 실제 지출 이메일 알림 저장 확인. 과금 중단 기능은 설정하지 않았다.
- 사용자 승인 후 새 Supabase DB에서 `supabase-bootstrap.sql`을 transaction으로 실행, 성공 확인.
  vector 0.8.2 활성화, schema 소유자·runtime USAGE/DDL 금지·anon/authenticated 접근 차단·역할 경계를
  `verify-supabase-bootstrap.sql`로 조회해 `all_checks_ok=true`를 확인했다.
- 비밀번호 생성·등록은 사용자 실행 단계로 남겼다. `bootstrap_cloud_secrets.py`는 초기 전용 환경만 허용하며
  admin 비밀번호를 숨김 입력으로 받고 로컬 libpq SCRAM hashing, 인증서 검증, stdin secret 등록을 사용한다.
  해당 credential helper의 외부 실행 성공은 아직 주장하지 않는다. 실패 후 일부 DB/secret 변경이 남을 수 있어
  기존 서비스/secret version이 있으면 재실행을 차단한다. 실패 시 메타데이터를 확인하고 수동 복구해야 한다.
- 최초 helper 실패 후 Secret version은 모두 0개, Cloud Run 서비스도 0개였다. 비밀번호 없이 TLS를 재현해
  시스템 CA 사용 시 체인 검증 실패를 확인했다. Dashboard의 공식 공개 CA 사용 후 chain/hostname 검증은 성공했다.
  helper와 API 이미지에 해당 CA 경로를 적용했다. 사용자가 변경한 관리자 비밀번호로 helper를 실행해
  DB 역할 credential 설정과 세 secret 등록을 완료했고, 세 version 1의 enabled 상태를 메타데이터로 확인했다.
  앱 역할 로그인·migration 및 Cloud Run 배포는 아직 검증하지 않았다.
- 승인된 네 Secret 읽기 binding은 version 1 조건을 사용한다. 실제 workload의 접근·거부 검증과
  GitHub WIF/deploy 권한 연결은 남아 있다.

## 학습 포인트

같은 출처 proxy는 브라우저 cookie 정책을 단순화하지만 서버 인가를 대체하지 않는다. 두 container는
한 revision으로 교체되어 release 정합성이 단순해지는 대신 독립 scaling이 어렵고 양쪽 자원이 청구된다.
트랜잭션 pooler 앞의 NullPool은 애플리케이션의 유휴 연결 중복을 줄이지만 동시 DB 작업 제한을 대신하지 않는다.
실패 시 application traffic 복구도 이미 적용된 schema를 되돌리지 못하므로 migration은 이전 앱과의 호환성이 필요하다.
면접에서는 “왜 두 service 대신 sidecar인가”, “pooler와 prepared statement가 충돌하는 조건은 무엇인가”,
“migration 성공 후 앱 실패 시 무엇을 복구할 수 있는가”를 현재 manifest와 테스트로 설명할 수 있어야 한다.
