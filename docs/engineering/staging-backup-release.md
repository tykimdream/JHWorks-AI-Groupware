# staging 백업·복원과 일반 release 검증

기준 main: `391d3a2fc62146cde5008acff6e92bba355ab2e0` (사용자 PR #20 병합).
[main CI 39612687196](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39612687196) 성공.
아래 준비/실제 실행/미검증을 구분한다. 공개/production 배포 작업이 아니다.

## 문제와 완료 조건

DB는 이미 head `b63d91e52fa0`까지 migration됐으므로 빈 DB bootstrap을 재사용할 수 없다.
일반 release 전에 복구 가능한 논리 백업과 격리 복원 증거가 필요하다. 완료 조건은 다음과 같다.

1. 승인된 전용 Supabase의 `groupware`만 읽기 전용 일관 스냅샷에서 pg_dump.
2. 외부 network/port/영구 volume이 없는 별도 DB에서 restore하고 원본과 비교.
3. row 수·내용 해시, column/default, FK/check/unique 제약, index, owner/ACL/default ACL,
   sequence 상태 및 migration head 일치. 실제 값·비밀번호는 로그/Git에 넣지 않는다.
4. 검증된 dump SHA256·보관 위치·시각을 일반 release의 backup reference로 연결.
5. exact main CI → private migration job → 새 revision → deploy SA WIF smoke 성공.

## 대안과 선택

유료 관리형 DB/새 cloud VM은 만들지 않는다. Cloud Shell의 기존 무료 Docker daemon을 사용한다.
Windows 로컬 Docker daemon은 여전히 없었다. Cloud Shell의 pg_dump 16은 원본 PostgreSQL 17과
major가 맞지 않아, 공식 pgvector 0.8.2-pg17 image를 내려받아 immutable digest로 고정한다.
기존 runtime/migration DB 역할과 인증서 검증을 유지한다. 새 IAM/Secret/DB 역할은 만들지 않는다.

`staging_backup.py`는 staging project/number, migration session pooler 5432, role 이름과 공개 CA를
확인한다. 기존 Secret version 1은 subprocess 메모리로만 읽고 libpq 연결/환경으로 전달한다.
원본 connection은 REPEATABLE READ/READ ONLY이며 pg_export_snapshot을 pg_dump에도 전달한다.
복원 DB는 network=none, CPU 1/메모리 512MiB, Unix socket peer 인증과 host reject를 사용한다.
생성한 고유 이름의 임시 container만 종료하며 원본 DB/기존 container/backup은 삭제하지 않는다.

복원용 역할은 해당 임시 DB 안에 NOLOGIN으로만 생성한다. 운영 계정의 새 비밀번호를 설정하지 않는다.
백업 subdirectory 0700·dump/report 0600, 기존 archive 덮어쓰기 금지, table당 10,000행 제한을 둔다.
큰 DB를 이 단기 실험 도구로 무제한 읽지 않고 별도 자원 검토를 요구한다.

## 준비 확인

- Cloud Shell Docker server 29.8.2, home 여유 약 4.4GB 확인.
- 기존 bootstrap venv의 psycopg를 재사용한다. 새 application library를 추가하지 않는다.
- pgvector image digest: `sha256:feb68f4f15446397d8cac7f4fe48fe4586de83160d1fc48b46283312d1a33966`.
- 로컬 unit 12개, Ruff와 strict mypy 통과. URL/role/TLS/CA 경계, row limit,
  순서에 무관한 내용 해시, mutable image 차단과 실패 시 secret stderr 비노출을 검증했다.
- Windows checkout의 CRLF PEM도 같은 공개 CA로 인식하도록 LF 정규화 후 pin을 비교한다.

## 실행 결과

원본에서는 sequence를 composite row로 바꿀 수 없어 첫 metadata 조회가 42809로 중단됐다.
원문/credential 없이 SQLSTATE와 쿼리 구간으로 원인을 좁혔다. sequence의 `last_value`/`is_called`를
명시적으로 읽도록 수정하고 해당 회귀 테스트를 추가한 뒤 아래 실제 검증에 성공했다.

| 확인 | 실제 결과 |
| --- | --- |
| backup ID | `20261021T141127Z-7cfefa98` |
| Cloud Shell 보관 | `~/jhworks-staging-backups/20261021T141127Z-7cfefa98/groupware.dump` |
| SHA256 | `d5aec3e814cafcc2b875c1c5deb6be3b3cbc1fdda84307bb146925abd7b80db4` |
| 크기/시간 | 39,501 bytes, dump 11.39초, isolated restore/비교 8.73초 |
| 원본/복원 일치 | head `b63d91e52fa0`, table 11개, columns/default/제약/index/owner/ACL/default ACL/row/sequence |
| 데이터 | alembic_version 1행, 업무 table 10개는 모두 0행 |
| 접근·자원 | subdirectory 0700/dump 0600 확인. 고유 임시 container 종료, 잔존 rehearsal container 없음 |
| 실제 reference | `cloud-shell:20261021T141127Z-7cfefa98:sha256:d5aec3e814cafcc2b875c1c5deb6be3b3cbc1fdda84307bb146925abd7b80db4:restore-verified` |

소규모 실험의 관측 시간이며 RTO 목표 달성/성능 개선율로 표현하지 않는다. dump/restore 검증은
source snapshot 기준이며 이 시점 이후 변경까지 포함하지 않는다. 신규 도구는 외부 Git에 아직 push하지 않았다.

## 일반 release 준비

GitHub 조회에서 `staging` Environment가 404이고 environment 목록도 비어 있음을 확인했다.
저장소 admin 권한은 유지됐다. 사용자 확인 후 **main 전용·Required reviewers 없음**으로 복원했다.
Environment ID `24927194153`, branch policy는 main branch 하나, protection rule은 branch_policy만 있다.
기존 repository variable 다섯 개와 CD_ENABLED=true를 확인했다. WIF/GCP IAM/Secret 권한은 바꾸지 않았다.

검증된 위 backup reference로 [일반 release 39615588202](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39615588202)를
dispatch했다. `bootstrap=false`이며 추가 owner 승인 없이 runner가 시작됐다. 새 SHA의 중복 실행과
동시 release 부재·exact main CI 성공을 확인한 뒤 한 번만 실행했다.

### 실제 release 실패와 복구

해당 run은 application 단계 `CalledProcessError`로 실패했다. Migration과 새 revision 생성은 진행됐고
새 `jhworks-staging-391d3a2fc621`는 Ready다. 자동 traffic rollback 후 GCP를 별도로 조회해
이전 `jhworks-staging-dfff250e6209`에 **100%**가 연결된 것을 확인했다.
release record에는 `rollbackTraffic=restored`, `rollbackErrorType=CalledProcessError`가 남았다.
CI rollback smoke 성공으로 표현하지 않는다.

2026-10-21 14:28:19 UTC에 기존 로그인 Cloud Shell 사용자 ID token으로 별도 HTTP smoke를 실행해
liveness 200, readiness 200, 앱 미로그인 경계 401, web 200의 **4/4**를 통과했다.
이것은 기존 서비스의 복구 확인이며 GitHub deploy SA의 WIF smoke 증거가 아니다.
원시 release record와 화면은 ignored `artifacts/cloud-run/`에 보관한다.

`smoke` 결과가 없고 정상/복구 양쪽의 명령 실행이 실패했으므로 ID token 발급이 유력한 원인이다.
Cloud Shell의 설치된 gcloud 소스에서 `--audiences`는 impersonated/service-account/GCE credential만
허용하는 분기를 확인했다. 기존 workflow는 Action의 external-account credential file을 사용하면서
일반 `gcloud auth print-identity-token --audiences`를 호출했다. 실패 기록에 명령명이 없어
이번 실행의 정확한 실패 명령은 확정하지 못했다. 새 진단 필드로 다음 실행에서 구분한다.

### 로컬 수정과 남은 검증

- 기존 `google-github-actions/auth@v3`를 이미지 build 뒤 다시 실행해 `token_format=id_token`,
  검증된 frontend origin audience, 기존 deploy SA로 token을 받는다. IAM/장기 키를 추가하지 않는다.
- token은 release step 환경변수로만 전달해 정상/복구 smoke에 사용한다. GitHub 실행에서 token이
  없으면 migration 이전에 중단한다. release JSON에는 token·원문 stderr를 기록하지 않는다.
- 실패 record에 고정된 `errorOperation`/`rollbackErrorOperation`을 추가한다. 서비스 교체/traffic/
  origin/token/smoke 실패를 account/credential 원문 없이 구분한다.
- 로컬 회귀 테스트는 Action token 사용·rollback·빈 token 차단·CI token 누락·원문 비노출을 검증한다.

Action 문서상 ID token 최대 수명은 10분이다. build 뒤 발급해 소모 시간을 줄이지만 이 token은
자동 갱신되지 않는다. 긴 migration/rollout/복구로 만료되면 HTTP 검증은 실패하며 성공으로 처리하지 않는다.
traffic 복귀와 HTTP 복구 확인은 별도 필드이며 후자가 실패하면 인증된 운영자 확인이 필요하다.
장시간 release를 지원하려면 migration/rollout 단계 분리와 fresh token 재발급을 추가 검증해야 한다.
현재 수정은 로컬 구현이며 실제 GitHub WIF 발급/새 release 성공은 PR 병합 뒤 확인해야 한다.
immutable SHA tag를 이미 push했으므로 실패한 동일 SHA를 무작정 rebuild/re-run하지 않는다.

최종 로컬 검증: API **213 passed / 16.07초**, Ruff app/tests/alembic 통과,
strict mypy app/tests 108 source files 통과. workflow YAML parsing과 build 뒤 token 발급 step 순서도 확인했다.
웹 코드는 변경하지 않았으며 이번 변경의 web build/E2E/container CI는 외부 push 이후 실행해야 한다.
실제 성공한 dump 이후 COUNT를 최대 10,001행까지만 읽도록 제한한 변경은 위 회귀 테스트로 검증했다.

## 학습 포인트

백업 파일 생성만으로 복구 가능성을 증명하지 못한다. 이 코드에서는 같은 exported snapshot의 원본과
격리 DB 복원 결과를 비교해 FK/index뿐 아니라 owner/ACL까지 확인했다. 스키마가 같아도 권한이 빠지면
배포 후 runtime 계정이 읽거나 저장하지 못하기 때문이다. 반대로 이 비교는 아직 업무 데이터 0행 기준이다.

면접에서는 “서로 다른 시점의 dump와 COUNT를 비교하면 어떤 문제가 생기는가”, “sequence는 왜
repeatable-read snapshot과 다를 수 있는가”, “IAM access token과 Cloud Run ID token audience는
어떻게 다른가”를 실제 실패 기록과 연결해 설명할 수 있다. 작은 실습은 로컬 격리 DB에 합성 행을 넣고
한 행/ACL/sequence를 각각 바꿔 어떤 비교가 실패하는지 확인하는 것이다. 외부 staging에는 수행하지 않았다.

## 검증 한계와 다음 작업

이 도구는 소규모 합성 staging의 **단기 수동 rehearsal**이다. Cloud Shell home은 장기 백업 저장소나
예약 백업/SLA를 제공하는 구성으로 간주하지 않는다. 암호화된 별도 보관·보존/회수·알림·주기적 복원은
별도 운영 단위다. 적은 데이터의 복원 시간은 대용량 RTO/RPO 달성을 증명하지 않는다.
pg_dump schema scope는 Supabase auth/storage/관리형 역할/플랫폼 설정을 포함하지 않는다.
원본 업무 transaction 재현과 공개 demo 격리는 별도로 검증해야 한다.
sequence 값은 MVCC snapshot과 별개로 진행될 수 있다. 동시 쓰기로 덤프와 비교값이 다르면 이 도구는
검증 실패로 중단하며, 업무 쓰기를 자동 중단하거나 원본 값을 되돌리지 않는다.

## 근거

- [PostgreSQL pg_dump](https://www.postgresql.org/docs/17/app-pgdump.html)
- [공식 pgvector image 빌드](https://github.com/pgvector/pgvector/blob/master/Makefile)
- [Cloud Shell 저장소](https://docs.cloud.google.com/shell/docs/using-cloud-shell)
- [Google auth Action: ID token과 WIF](https://github.com/google-github-actions/auth#inputs-generating-id-tokens)
