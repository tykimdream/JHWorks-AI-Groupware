# Cloud Run + Supabase 첫 배포 단위

상태: 로컬 구현·검증 완료, 외부 배포 미검증, 2026-10-21. 기존 Phase 0 진단과 별도 변경 단위다.
실행 결과와 한계는 [검증 기록](cloud-run-supabase-verification.md)에 둔다.

## 이번 단위의 완료 조건

- Next.js가 `/api/v1`을 같은 instance의 FastAPI로 proxy한다. 브라우저가 API 별도 도메인에
  의존하지 않으며 login cookie·Origin·request ID·기존 휴가 workflow를 로컬 E2E로 검증한다.
- Cloud Run의 두 container를 한 revision으로 배포할 manifest를 생성한다. 웹만 ingress port를
  갖고 API startup probe 통과 뒤 웹이 시작한다. 최소 instance 0, 제한된 최대 instance/concurrency,
  고정 digest image·secret version·전용 service account를 사용한다.
- Supabase transaction pooler를 위한 NullPool과 psycopg prepared statement 비활성화를 지원한다.
  migration은 별도의 session pooler credential과 일회성 job을 사용하며 seed는 자동 실행하지 않는다.
- Cloud Run release는 migration→배포→인증된 읽기 smoke 순서다. 실패 시 이전 revision traffic 복구,
  migration 자동 downgrade 금지, 첫 배포 실패는 복구 대상 없음으로 명시한다.
- 유료 자원 생성/secret 값 전송/외부 배포는 이번 로컬 검증에 포함하지 않는다.

## 선택과 대안

두 독립 Cloud Run service는 독립 scaling에 유리하지만 browser의 cross-site cookie 또는
web→private API 인증 연결이 필요하다. 현재 한 제품·낮은 트래픽·동일 release 단위에서는
web ingress + API sidecar가 더 작은 구조다. 두 container의 CPU/메모리는 모두 과금 대상이며
단일 service가 절반 가격이라는 뜻은 아니다. 병목/배포 주기가 갈리면 별도 service를 재검토한다.

Firestore 전환이나 Supabase browser DB 직접 접근은 하지 않는다. 기존 FastAPI가 인증·권한·확인·
transaction 경계를 유지하고 Supabase는 PostgreSQL 호스팅으로 사용한다. Data API 노출 방지는
별도의 Supabase 설정 검증이 필요하다.

## 후속 공개 gate

첫 배포 구성은 IAM으로 보호된 staging 준비다. 포트폴리오 방문자 공개 전에는 세션별 합성 데이터 범위,
로그인/업무 호출 제한, DB Data API 권한, backup/restore, 실제 TLS와 cookie를 검증한다.
이번 배포 구성은 AI key를 주입하지 않고 AI를 명시적으로 끈다. 이후 별도 단위로 OpenAI 전용 project,
공유 DB의 원자적 예산 예약/정산·방문자/전체 제한·provider hard limit·한도 후 수동 fallback을 구현한다.
기존 timeout/출력 token/Tool round 제한만으로 비용 상한을 보장한다고 주장하지 않는다.

대용량 실험은 로컬 전용 DB와 fake AI에서 수행한다. 공개 DB/Cloud Run에 부하를 보내지 않는다.

## 외부 상태 확인

사용자가 로그인한 앱 안 브라우저에서 결제 연결을 읽기 전용 확인했다. 연결된 기존 네 프로젝트에
JHWorks 그룹웨어 전용 프로젝트는 없었다. 이후 전용 GCP 프로젝트 `jhworks-staging-tykimdream`을 생성했다.
콘솔에서 기존 결제 계정 연결과 초기 예상 요금 0원을 확인했다. 이후 사용자 승인으로 API 활성화,
전용 예산 알림과 서울 Docker 저장소 `jhworks`를 생성했다. 실제 서비스 배포는 아직 수행하지 않았다.
기존 프로젝트/다른 서비스의 자원·데이터는 변경하지 않는다.
Supabase는 사용자가 전용 `jhworks-staging` Free 프로젝트를 서울(`ap-northeast-2`)에 생성했다.
초기 준비 후 Healthy 상태와 Data API 비활성을 확인했다. SQL Editor 읽기 조회에서 PostgreSQL 17.11,
pgvector 가용 버전 0.8.2를 확인했다. 앱의 pooler 연결·migration 검증은 아직 대기 중이다.
계정·결제 ID나 비밀 값은 문서에 넣지 않는다.

## 참고

- [Cloud Run multi-container와 startup order](https://docs.cloud.google.com/run/docs/configuring/services/containers)
- [Cloud Run runtime contract](https://docs.cloud.google.com/run/docs/container-contract)
- [Supabase SQLAlchemy pooler 지침](https://supabase.com/docs/guides/troubleshooting/using-sqlalchemy-with-supabase-FUqebT)
- Next 16.3.8 설치 패키지의 `dist/docs/01-app/03-api-reference/05-config/01-next-config-js/rewrites.md`
