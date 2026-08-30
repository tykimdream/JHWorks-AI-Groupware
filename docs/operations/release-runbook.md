# JHWorks Release and Rollback Runbook

## 1. 적용 범위

이 문서는 immutable OCI image, managed PostgreSQL/pgvector, TLS endpoint를 사용하는 배포를 기준으로 한다.
특정 cloud provider의 버튼이나 서비스명에 의존하지 않고 release job, API/web workload, secret manager와
traffic switch라는 공통 경계를 사용한다. 로컬 `docker-compose.yml`은 같은 순서를 재현하는 rehearsal 환경이다.

배포 권한과 DB backup 권한은 분리한다. AI API key가 없어도 core groupware를 배포할 수 있으며, demo seed는
production release 절차에 포함하지 않는다.

## 2. Release 불변 조건

- API와 web image는 commit SHA tag와 registry digest로 고정한다. `latest`만으로 배포하지 않는다.
- migration은 API replica 기동과 분리된 single-run release job에서 먼저 수행한다.
- 새 migration은 구버전 application과 함께 동작하는 expand 단계여야 한다.
- production 설정은 [production.env.example](../../deploy/production.env.example)의 이름을 기준으로 secret/config manager에서 주입한다.
- release 전 DB backup 또는 복구 가능한 snapshot ID를 확보한다.
- traffic 전환 후 [deployment smoke](../../apps/api/app/ops/deployment_smoke.py)가 통과해야 완료로 기록한다.

## 3. Release 절차

### A. 후보 검증과 image 고정

```bash
pnpm validate
pnpm eval:all                 # model/prompt/retrieval 변경 시 필수
docker build -f apps/api/Dockerfile -t REGISTRY/jhworks-api:COMMIT_SHA .
docker build \
  --build-arg NEXT_PUBLIC_API_URL=https://api.groupware.example.com/api/v1 \
  -f apps/web/Dockerfile -t REGISTRY/jhworks-web:COMMIT_SHA .
```

registry에 push한 뒤 두 digest, commit SHA, CI run과 평가 report를 release record에 남긴다. image scan의 high
severity finding이 해결되지 않았으면 중단한다.

### B. DB 보호와 migration

1. managed PostgreSQL backup/snapshot을 생성하고 복구 가능 상태를 확인한다.
2. 새 API image와 production secret을 사용하는 일회성 job을 실행한다.

```bash
alembic upgrade head
alembic current
```

3. job은 정확히 한 번 성공해야 한다. 실패하면 API traffic을 전환하지 않고 migration log와 DB 상태를 확인한다.
4. `python -m app.scripts.seed`는 synthetic local demo 전용이다. production에서는 실행하지 않는다.

### C. Workload와 traffic

1. 새 API image를 readiness gate 뒤에 배포한다.
2. `/api/v1/health/ready`가 DB check까지 통과한 replica만 traffic에 포함한다.
3. build-time API URL이 고정된 새 web image를 배포한다.
4. 새 revision에 소량 또는 전체 traffic을 전환한다.

### D. Smoke와 완료 판정

```bash
JHWORKS_SMOKE_API_URL=https://api.groupware.example.com/api/v1 \
JHWORKS_SMOKE_WEB_URL=https://groupware.example.com \
pnpm smoke:deployment
```

smoke는 liveness, DB readiness, `X-Request-ID`, 비인증 `401` 경계와 web root를 읽기 전용으로 검사한다.
`artifacts/smoke/latest.json`의 4/4 통과, error rate와 latency의 비정상 증가 없음, 새 revision의 startup error
없음을 확인하면 release를 완료한다.

## 4. Rollback

다음 중 하나면 새 traffic을 중단하고 직전 digest로 되돌린다.

- readiness 또는 smoke 실패
- 인증/인가 경계 변화
- Approval/Leave 상태 전이 오류
- 지속적인 5xx 또는 DB constraint 오류

### Application rollback

1. 새 revision으로의 traffic 확대를 멈춘다.
2. 직전 API/web digest를 다시 배포한다.
3. 동일 smoke를 실행하고 request ID로 오류 구간을 확인한다.
4. 실패 release의 image, migration revision, logs와 smoke report는 조사용으로 보존한다.

### Database rollback 원칙

incident 중 `alembic downgrade`를 자동 실행하지 않는다. additive migration이면 직전 application이 새 schema를
무시하도록 유지하고 application만 rollback한다. destructive/incompatible schema가 이미 적용됐다면 write traffic을
중지하고, 사전에 검증한 forward-fix 또는 snapshot restore 중 데이터 손실이 적은 경로를 incident owner가 선택한다.

snapshot restore가 필요한 경우 복구 시점 이후의 write 손실 범위와 Approval/Leave 회계 일관성을 먼저 기록한다.
복구 후에는 migration revision, `leave_accounts` 합계, PENDING ApprovalLine과 LEAVE calendar 1:1 관계를 검증한다.

## 5. 운영 증거와 보안

- 외부 ticket에는 request ID, release digest, stable error code와 발생 시각만 기록한다.
- cookie, confirmation token, prompt 원문, DB URL, provider 오류 message는 첨부하지 않는다.
- JSON exception log는 exception type과 frame만 사용한다.
- OpenAI 장애 시 AI endpoint의 안전한 `503`과 core groupware 정상 동작을 별도로 확인한다.
- secret rotation 후에는 기존 session 만료 영향과 새 로그인, readiness, smoke를 확인한다.

## 6. 로컬 release rehearsal

Docker Compose v2가 있는 환경에서는 다음 명령이 실제 release 순서를 재현한다.

```bash
docker compose up --build --detach
pnpm smoke:deployment
docker compose down
```

Compose는 `migrate → seed → API readiness → web` 순서다. volume을 지우는 `docker compose down --volumes`는
synthetic local DB를 의도적으로 초기화할 때만 사용한다.
