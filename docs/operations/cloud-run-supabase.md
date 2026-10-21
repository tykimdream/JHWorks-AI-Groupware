# Cloud Run + Supabase staging release

상태: PR #18 병합 및 main CI 성공 후 첫 private release를 실행했다.
PR #19 병합 후 실제 migration/service Ready 및 별도 수동 smoke 4개를 검증했다.
CI release는 GCP가 반환한 URL 별칭을 거부해 실패했다. 동일 서비스의 URL 목록을 검사하는
로컬 수정/테스트를 완료했다. 정상 CI release와 WIF audience smoke/업무 로그인/저장은 후속이다.
service/revision max=2, min=0을 재조회했고 AI/공개 접근은 꺼져 있다. 최신 결과는
[첫 배포 기록](../engineering/staging-rehearsal.md)을 기준으로 확인한다.

2026-10-21 사용자가 전용 GCP 프로젝트 `jhworks-staging-tykimdream`에서 서울 Cloud Run private staging
1개(min=0/max=2, web/API 각 1 CPU·512MiB), migration Job, Artifact Registry 1개, Secret Manager 3개,
5천원·1만원 예산 알림 구성과 private staging 배포를 승인했다. 월 1만원은 목표이며 hard cap이 아니다.
Supabase Free는 사용자 생성 완료, 서울 리전이다. 공개 전환·유료 DB·AI 연결은 승인 범위에 포함되지 않는다.
실제 credential 입력과 보안 권한 부여는 해당 단계의 범위를 별도 확인한다.
GCP 프로젝트 전용 `jhworks-staging-monthly-10000krw` 예산을 실제 저장하고 월 1만원·50%/100% 실제 지출
알림 및 결제 관리자/프로젝트 소유자 이메일 수신 설정을 확인했다. 알림 전용이며 enforced spend cap은 설정하지 않았다.
무료 할당은 결제 계정의 다른 프로젝트와 공유된다. 사용자가 Cloud Shell 권한을 승인했고 활성 계정 연결을 확인했다.
Cloud Run/Artifact Registry/Secret Manager/IAM/IAM Credentials/STS API 활성화와 서울의 Docker 저장소
`jhworks` 생성에 성공했다. 저장소는 immutable tags 설정이며 첫 release에서 web/API SHA tag와 digest를 올렸다.
Supabase는 Healthy 상태, Data API 비활성, SQL Editor의 읽기 전용 조회로 PostgreSQL 17.11과
pgvector 0.8.2 설치 가능 상태를 확인했다.
이후 사용자 승인으로 bootstrap SQL을 실행했고 vector 0.8.2 활성화와 schema/role 경계의
`all_checks_ok=true`를 확인했다. 실제 앱 migration은 아직 실행하지 않았다.

초기 비밀번호/secret 등록은 `app/ops/bootstrap_cloud_secrets.py`를 사용자가 직접 실행한다.
기존 psycopg 3.3.4와 gcloud가 필요하다. 새 전용 환경만 허용하며 기존 서비스/secret version을 발견하면 차단한다.
admin 비밀번호는 getpass로 입력받고 로컬 SCRAM verifier를 생성해 SQL에 평문 비밀번호를 넣지 않는다.
두 DB 비밀번호와 JWT secret은 무작위 생성되어 GCP의 승인된 보관함에 stdin으로 전송된다.
파일·터미널·프로세스 인자에 값은 쓰지 않는다. 공식 Supabase CA와 hostname 검증을 통과해야 한다.
연결 실험에서 시스템 CA만 사용하면 Supabase pooler가 `self-signed certificate in certificate chain`으로
거부됐다. Dashboard > Database > Settings의 공식 CA 다운로드를 사용해 동일 endpoint의 chain/hostname
검증이 `Verify return code: 0 (ok)`로 통과했다. `supabase-ca-2021.crt`는 공개 인증서이며
SHA256 `700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7`다.
API/migration 이미지에 `/workspace/certs/supabase-ca-2021.crt`로 포함하고 URL의 sslrootcert도 맞춘다.
초기화 도구의 관리자 연결은 `--ca-file`(기본 Cloud Shell 홈의 `jhworks-supabase-ca.crt`)을 사용한다.
인증서 검증 비활성화나 시스템 전체 trust store 변경은 하지 않는다.
최초 helper 실행은 실패했고 이후 확인한 Secret version은 세 보관함 모두 0개였다. 서비스도 없었다.
실패 코드는 비밀 내용을 출력하지 않고 TLS/인증/권한/타임아웃을 분류하며 GCP preflight를 비밀번호 입력 앞으로 옮겼다.
사용자가 관리자 DB 비밀번호 변경 후 수정된 helper를 직접 실행했다. `database_credentials`와 세 secret 등록
단계를 완료했고 `Credential setup complete`를 확인했다. 메타데이터로 세 보관함의 version 1이 모두 enabled임을
확인했다. 비밀 값은 조회하지 않았다. 실제 앱 역할 로그인·migration·서비스 배포는 별도 검증이 남아 있다.
이후 사용자 승인으로 runtime 계정에는 runtime DB/session secret, migrate 계정에는 migration DB/session
secret의 Secret Accessor를 Secret별로 부여했다. 각 binding에 `resource.name.endsWith('/versions/1')`
조건을 사용했다. IAM 설정 반영을 확인했으며 실제 workload의 접근 허용/거부는 배포 검증에서 확인한다.
Cloud Shell 전용 venv에 기존 psycopg 3.3.4를 설치했고 준비한 스크립트의 문법과 로컬 소스 일치 해시를 확인했다.
사용자가 명령 제출·SETUP 확인·숨김 비밀번호 입력을 직접 수행하도록 실행 직전 상태로 인계했다.
실패 시 DB 비밀번호 변경과 secret 등록이 부분 완료될 수 있다. 재실행으로 덮지 말고 메타데이터 확인 후 복구한다.
참고: [PostgreSQL 비밀번호 변경 주의](https://www.postgresql.org/docs/17/sql-alterrole.html),
[libpq encrypt_password](https://www.psycopg.org/psycopg3/docs/api/pq.html#psycopg.pq.PGconn.encrypt_password).

## 구성과 현재 경계

```text
방문자 ──HTTPS── Cloud Run service (현재 IAM 보호, min=0/max=2)
                   ├─ web: Next standalone, ingress 3000
                   │    /api/v1/* → http://127.0.0.1:8000/api/v1/*
                   └─ api: FastAPI, startup DB ready / liveness process
                              │ TLS + Supabase transaction pooler
                         private groupware schema

GitHub CI → staging Environment 승인 → 이미지 digest → migration job → revision → smoke
```

하나의 Cloud Run service 안의 두 container다. Docker Compose 파일을 Cloud Run에 그대로 올리지는 않는다.
두 container의 CPU/메모리는 모두 과금 대상이며, 초기 1만원 예산은 목표이지 과금 상한이 아니다.
API 공개 endpoint·로드밸런서·VPC NAT·Supabase 유료 IPv4 add-on은 이 안에 포함하지 않는다.

웹 build 시 다음을 고정한다. `API_PROXY_TARGET`은 build-time 설정이며 browser가 전달할 수 없다.

```text
NEXT_PUBLIC_API_URL=/api/v1
API_PROXY_TARGET=http://127.0.0.1:8000
```

## 1. 실제 생성 전에 확정할 항목

- 그룹웨어 전용 GCP project와 결제 연결. 기존 다른 제품 project는 재사용하지 않는다.
- Cloud Run/Artifact Registry region은 Supabase의 제공 지역·지연을 함께 확인해 결정한다.
  이번 전용 환경은 사용자 승인 후 Cloud Run `asia-northeast3`, Supabase `ap-northeast-2`로 확정했다.
- Supabase Free project 1개. 유료 plan·IPv4 add-on·자동 업그레이드에 동의하지 않는다.
- Cloud Run min=0, max=2, concurrency=8부터 시작. 이미지 보관/로그 보존·전송량도 관측한다.
- GCP 월 1만원 목표 알림과 실제 사용량 확인 절차. OpenAI key는 이번 release에 연결하지 않는다.
  공개 AI의 별도 월 $5 제안은 예산 예약/정산 구현과 provider 설정 확인 후 적용한다.

이 문서/예제 실행만으로 cloud 자원이 생기지는 않는다. 이후 enable API/registry/secret/IAM/서비스 생성은
명시적으로 승인한 전용 project에서만 수행한다. 설정 값/비밀번호/token은 chat이나 Git에 붙이지 않는다.

## 2. Supabase DB 준비

기존 Alembic migration을 유지한다. 브라우저가 Supabase Data API로 업무 DB에 직접 접근하지 않는다.
`deploy/cloud-run/supabase-bootstrap.sql`을 사용자 승인 후 새 synthetic project에서 한 번 실행했다.
`verify-supabase-bootstrap.sql`의 읽기 조회를 통과했다. 향후 업무 테이블의 기본 권한과 앱 migration은 별도로 검증한다.

- 관리자로 vector extension 활성화, private `groupware` schema와 runtime/migration role 분리.
- role의 LOGIN password는 사용자가 초기 설정 도구를 직접 실행해 설정한다. SQL 파일에는 값이 없다.
- `groupware`를 Supabase exposed schemas에 추가하지 않는다. anon/authenticated가 읽을 수 없는지
  실제 Data API 요청과 DB 권한 테스트로 확인한다. UI에서 table을 숨기는 것만으로 완료하지 않는다.
- runtime URL: transaction pooler(6543), `postgresql+psycopg`, `sslmode=require` 이상.
  `JHWORKS_DATABASE_POOL_MODE=null`과 `JHWORKS_DATABASE_DISABLE_PREPARED_STATEMENTS=true`를 사용한다.
  TLS hostname 검증(`verify-full`)에 필요한 CA 제공 방법은 실제 project에서 확인한다.
- migration URL: 별도 migration role과 session pooler(5432) 또는 연결 가능한 direct endpoint.
  외부 IPv4 add-on을 자동 구매하지 않는다. 연결은 TLS를 사용한다.
- DB password의 `@`, `%` 등은 URL-encode한다. Alembic의 ConfigParser interpolation도 처리한다.

runtime은 필요한 DML만 허용하고 schema owner/admin password를 배포 runtime에 주지 않는다.
Supabase auth/service_role key를 DB connection password 대신 사용하지 않는다.
seed/reset은 release job에서 실행하지 않는다. 첫 synthetic 초기화는 실제 공개 데모 데이터 정책을
정한 후 별도 검토한 작업으로 수행하며 기존 사용자/조직 데이터는 사용하지 않는다.

## 3. Secret과 service account

Secret Manager에는 runtime DB URL, migration DB URL, 세션 JWT secret을 서로 다른 secret으로 저장한다.
예제는 값 대신 이름과 숫자 version만 가진다. secret version `latest`는 release에서 거부한다.

- runtime service account: runtime DB/JWT secret의 해당 version만 읽을 수 있도록 부여.
- migration service account: migration DB/JWT secret을 읽고 job에서만 사용.
- deploy service account: 승인된 registry writer, 해당 staging service/job deploy 권한,
  위 두 service account에 대한 제한된 `iam.serviceAccounts.actAs`, private service invoker.
- GitHub WIF: 정확한 `tykimdream/JHWorks-AI-Groupware`, main branch와 staging Environment로
  attribute 조건을 제한한다. GitHub subject에 staging environment가 들어가는 점을 확인한다.
  service account JSON key를 발급하지 않는다. OIDC identity token의 audience는 service URL이다.

권한 부여는 그 자체가 외부 보안 설정 변경이므로 별도 실제 계정 설정 확인 후 적용한다.
deploy 역할은 project 전체 owner/editor 대신 필요한 권한 범위로 검토한다.

## 4. 비용 없는 manifest 생성

`settings.example.json`을 ignored `settings.local.json`으로 복사해 **비밀 값이 아닌 참조**만 채운다.
`frontend_origin`은 실제 고정 Cloud Run service URL(또는 검증한 domain)이어야 한다.
첫 생성 URL을 사전 산출/확인한 뒤 입력하며 placeholder로 외부 배포하지 않는다.
최초 실제 bootstrap에서 URL 불일치가 발생하면 서비스는 private 상태로 두고 원인을 확인한다.

```powershell
cd apps/api
uv run python -m app.ops.cloud_run --settings ../../deploy/cloud-run/settings.local.json `
  --api-image "REGION-docker.pkg.dev/PROJECT/REPO/api@sha256:DIGEST" `
  --web-image "REGION-docker.pkg.dev/PROJECT/REPO/web@sha256:DIGEST" `
  --commit "FULL_40_CHARACTER_COMMIT_SHA" --output-dir ../../artifacts/cloud-run
```

실제 64자리 digest·40자리 SHA를 사용한다. 이 명령은 파일만 생성하며 네트워크/credentials를 사용하지 않는다.

## 5. 첫 staging CD 설정과 실행

`.github/workflows/cloud-run-staging.yml`은 **기본 비활성, main 전용, workflow_dispatch**다.
첫 단위는 승인형 CD다. 모든 main push의 자동 배포는 backup 자동화와 실제 staging rehearsal 후 별도 추가한다.
자동 배포가 이미 운영된다고 표현하지 않는다.

GitHub `staging` Environment는 현재 main 전용이며 required reviewer는 없다. 다음 값은 **repository variable**로
구성한다. `CLOUD_RUN_CD_ENABLED`는 Environment 진입 전 job의 `if`에서 읽으므로 Environment 전용
variable로만 설정하면 job이 실행되지 않을 수 있다. 비밀 값은 이 variable에 넣지 않는다.

| Variable | 내용 |
| --- | --- |
| `CLOUD_RUN_CD_ENABLED` | 자원·권한·비용 승인 후에만 `true` |
| `CLOUD_RUN_SETTINGS_JSON` | 검증한 settings JSON, 값 대신 secret 이름/version |
| `CLOUD_RUN_IMAGE_REPOSITORY` | `REGION-docker.pkg.dev/PROJECT/REPOSITORY` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | 승인한 WIF provider resource name |
| `GCP_DEPLOY_SERVICE_ACCOUNT` | deploy service account email |

사용자 승인 후 위 설정을 적용했고 CD flag를 true로 전환했다. 최초에는 `staging` reviewer를 저장소
소유자로 설정했으나, 이후 Environment가 삭제된 것을 발견해 사용자 확인 후 **main 전용·reviewer 없음**으로
복원했다. 현재 Run workflow 이후 추가 배포 승인은 요구하지 않는다. main push 자동 배포는 아직 없다.
WIF 초기 설정은 `deploy/cloud-run/bootstrap-github-wif.sh`와 같은 디렉터리의 role/condition 파일을
검토해 사용한다. 전용 프로젝트 ID/number를 고정하며, 이미 생성된 자원이 있거나 부분 실패하면
전체 스크립트를 다시 실행하지 말고 해당 자원을 조회한 뒤 필요한 단계만 복구한다.

이 저장소는 immutable OIDC subject를 사용한다. 실제 GitHub repository OIDC customization API에서
prefix를 조회해 `repo:tykimdream@53204415/JHWorks-AI-Groupware@1341433132:environment:staging`을
확인했다. 이전 이름 기반 subject는 실제 첫 release에서 거부됐다. 이를 교정한 attempt 2는 인증에 성공했다.
새 저장소/이름 변경/이전 시에는 [GitHub OIDC 문서](https://docs.github.com/en/actions/reference/security/oidc#immutable-subject-claims)와
실제 metadata를 비교한다. 조건을 없애거나 Owner/Editor 권한을 추가해 해결하지 않는다.

실행 전 staging DB의 복구 가능한 backup을 로컬 도구로 만들고 복원 검증한 참조를 준비한다.
Supabase Free의 managed backup을 가정하지 않는다. bootstrap은 새 빈 synthetic DB임을 확인한 경우만 사용한다.
`backup_reference`는 증거 기록이며 코드가 파일의 존재/복원 성공을 자동으로 증명하는 것은 아니다.

워크플로는 exact main SHA의 push CI 성공을 확인하고 이미지를 build/push한 뒤 immutable digest로 배포한다.
Migration job의 실패는 API rollout 전에 중단한다. 기존 service는 이전 traffic split을 보존한 채
candidate를 생성하고 readiness 뒤 traffic을 전환한다. private IAM 서비스에 identity token으로 smoke한다.
이미지 build 뒤 기존 Google auth Action에서 `id_token`을 발급해 release step 환경으로만 전달한다.
Action credential file과 일반 `gcloud auth print-identity-token --audiences`의 호환성을 가정하지 않는다.
GitHub 실행에서 token이 없으면 migration 전에 중단한다. 로컬 CLI의 gcloud fallback은 유지한다.
ID token은 최대 10분이며 자동 갱신되지 않는다. 장시간 rollout/복구 후 token 만료로 smoke가 실패하면
정상 배포/복구 완료로 간주하지 않고 인증된 운영자가 traffic와 HTTP를 따로 확인한다.
실제 GitHub token 발급 성공은 다음 main release에서 검증해야 한다.
첫 실제 provisioning에서 invoker IAM을 활성 상태로 유지하고 상위 project에 public invoker grant가 없는지 확인한다.
공개 IAM policy/비활성 invoker 체크가 있는 기존 서비스에는 이 staging runner가 배포하지 않는다.

### 승인 없는 staging 배포와 자동 배포의 차이

사용자가 매번 누르는 `Approve and deploy`는 저장소 Settings → Environments → staging의
Deployment protection rules → Required reviewers 설정에서 온다. 해당 reviewer 요구를 해제하고
Save protection rules를 누르면 Environment 수동 승인이 없어지며, main 전용 배포 branch 정책과
`environment: staging`, WIF 조건은 유지할 수 있다. Environment 자체를 삭제할 필요는 없다.
사용자가 이 방향을 명시적으로 승인해 현재 staging에는 적용했다. production 승인 설정은 추가하거나
변경하지 않았다. Environment 삭제 대신 main 제한을 유지한 구성을 사용한다.

이 변경만으로 main push 자동 배포가 생기지는 않는다. 현재 workflow는 `workflow_dispatch`만 받으므로
Run workflow를 누르면 추가 승인 없이 실행되는 수준이다. main 병합 후 자동 배포까지 원하면 별도 PR에서
성공한 main push CI의 완료 이벤트를 연결해야 한다. `workflow_run`을 사용한다면 PR/fork의 CI 완료는
배포하지 않고, event=push/main/성공/동일 저장소를 확인한 `head_sha`만 checkout·build·배포한다.
기본 `github.sha`와 완료된 CI의 SHA가 다를 수 있으므로 두 값을 혼용하지 않는다.

자동 배포의 DB backup reference도 실제 backup/restore 확인 결과에서 얻어야 한다. 빈 DB용 bootstrap을
매번 켜거나 가짜 참조를 넣지 않는다. 첫 staging 검증과 backup 자동화가 끝난 뒤 연결하고,
production Environment의 수동 승인은 별도로 유지하는 방향이다.

근거: [GitHub Environment 관리](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments),
[배포 보호 규칙](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments).

## 6. 실패·복구·증거

### 소규모 staging 수동 백업·복원

`apps/api/app/ops/staging_backup.py`는 승인된 전용 Supabase의 migration session pooler와 CA,
GCP 프로젝트 번호를 확인하고 `groupware`만 dump한다. Docker와 기존 psycopg/gcloud가 필요하다.
Cloud Shell에서 source와 동일한 파일을 실행했고 별도 유료 DB/VM을 생성하지 않았다.

```bash
python apps/api/app/ops/staging_backup.py \
  --image pgvector/pgvector@sha256:feb68f4f15446397d8cac7f4fe48fe4586de83160d1fc48b46283312d1a33966 \
  --ca-file "$HOME/jhworks-supabase-ca.crt" \
  --output-root "$HOME/jhworks-staging-backups"
```

도구의 JSON에서 status=passed, temporaryContainerRemoved=true와 실제 archive/checksum을 확인한
경우에만 backupReference를 사용한다. 복원 DB는 network=none/Unix socket peer 인증이며 원본 DB를
복원 대상으로 받지 않는다. dump 0600/subdirectory 0700을 실제 Linux에서 확인했다.
현재 rehearsal은 업무 데이터 0행의 작은 DB 기준이며 장기 보존·예약 백업·대용량 RTO 검증을 대체하지 않는다.
전체 DB의 auth/storage/관리 역할 복구도 포함하지 않는다.
[실행 기록](../engineering/staging-backup-release.md)에 실제 범위/해시/실패와 성공을 남긴다.

- 실패하면 이전 revision별 traffic 비율로 복귀하고 rollback smoke 결과를 기록한다.
- rollback smoke가 실패하면 복구 완료라고 주장하지 않고 release를 실패로 유지한다.
- 첫 배포에는 이전 revision이 없으므로 자동 삭제하지 않고 private service에서 진단한다.
- DB downgrade/데이터 삭제/초기화를 자동 수행하지 않는다. schema는 expand-compatible이어야 한다.
- release JSON에는 SHA/digest·backup 참조·traffic·검사 결과만 저장하며 secret/token/gcloud stderr를 넣지 않는다.
- private staging의 브라우저 진입 인증(IAP 등)은 아직 설정하지 않았다. 최초 cloud 검증은 인증된 HTTP smoke부터
  시작하고, 포트폴리오 URL의 익명 접근은 다음 공개 gate 이후 연다.

## 7. 공개 포트폴리오와 AI의 남은 gate

현재 기본 demo 계정은 그대로 공개하지 않는다. 세션별 합성 데이터 접근 범위·방문자 제한·입력 개인정보
안내·DB Data API 차단·복구 검증을 갖춘 뒤 공개한다. 공개 IAM 변경은 별도 승인한다.

AI는 manifest에서 key 주입 없이 `JHWORKS_AI_ENABLED=false`로 강제한다. 현재 kill switch는
누적 비용 제한의 구현이 아니다. 다음 단위는 provider 전용 project/키·일일/월 budget의 원자적 예약과 정산,
방문자별 제한, provider hard limit, 한도 후 AI만 차단하는 수동 업무 fallback이다.
공유 demo 계정 ID만으로 방문자 quota를 구분하지 않는다. Cloud Run의 재기동/여러 instance에서도
일관되도록 공유 DB에서 제한을 검증한다.

대용량/부하 실험은 로컬 Docker PostgreSQL과 fake AI를 사용한다. 실제 deployment DB/API URL이나
provider key를 실험 설정에 넣지 않는다. 일반 API/E2E 테스트는 외부 LLM을 호출하지 않는다.
