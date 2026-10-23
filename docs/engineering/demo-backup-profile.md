# 전용 데모 백업·격리 복원 프로필

## 문제와 선택

기존 `staging_backup`은 private `groupware`와 staging migration Secret으로 고정돼 있다.
그 백업은 이후 생성한 `groupware_demo`의 방문자 업무/피드백/공용 규정을 포함하지 않는다.
데모 정리 실험 전에 현재 자료를 복원할 수 있는지 별도로 확인해야 한다.

새 백업 시스템이나 임의 schema/Secret CLI 대신 같은 검증 경로에 두 개의 고정 profile만 둔다.
기본 `staging`은 기존 호스트/사용자/schema/Secret과 같고, 명시적 `--profile demo`만
`jhworks_demo_migrate`/`groupware_demo`/`jhworks-demo-migration-database` version1을 사용한다.
새 라이브러리·클라우드 자원·IAM·키 발급은 필요 없다. 복제 스크립트 두 개보다 보안 수정의 누락을 줄인다.
프로필을 잘못 선택하면 고정 URL 사용자와 실제 current_user/current_schema 검사에서 중단한다.
demo migration 역할에 private schema USAGE가 생겨도 dump 전에 중단한다.

## 실행 경계

실제 Secret 읽기와 원격 dump는 별도 인증 범위 확인 후 실행한다. 준비 단계에서 실행하지 않는다.
검증·병합한 고정 source/CA checksum을 대조하고 Cloud Shell에서 다음을 실행한다.
아래 image는 기존 staging 복원에 사용한 digest이며 새 demo 복원 성공을 뜻하지 않는다.

```sh
python -m app.ops.staging_backup \
  --profile demo \
  --image pgvector/pgvector@sha256:feb68f4f15446397d8cac7f4fe48fe4586de83160d1fc48b46283312d1a33966 \
  --ca-file "$HOME/jhworks-supabase-ca.crt" \
  --output-root "$HOME/jhworks-demo-backups"
```

- 기존 operator 권한으로 새 demo migration DB Secret v1만 프로세스 메모리에서 읽는다.
  staging DB/session 또는 demo session Secret payload를 읽지 않는다.
- 고정 Supabase session pooler5432/TLS verify-full/고정 CA를 유지한다.
  원본은 READ ONLY/REPEATABLE READ와 exported snapshot으로 읽고 `pg_dump --schema=groupware_demo`만 한다.
  pg_dump 비밀번호는 자식 환경에 전달하며 명령 인자/로그/보고서/저장소에 출력하지 않는다.
- 테이블당10,000행 제한은 대량 실험의 자원 검토를 대체하지 않는다. 데이터와 sequence의 동시 쓰기가
  있는 동안 sequence는 MVCC snapshot에 고정되지 않으므로 비교가 실패할 수 있다. 실패를 숨기거나
  자동 재실행하지 않고 조용한 시간에 원인을 확인한다.
- dump는 Cloud Shell private0700 폴더/0600 파일에 남긴다. 임시 Docker는 network=none,
  socket-only/peer auth/512MiB/CPU1이며 외부 포트·DB 비밀번호·원격 복원을 사용하지 않는다.
  종료 시 이번 실행의 고유 임시 컨테이너만 정리하고 dump/report는 보존한다.
- schema/컬럼/제약/인덱스/소유자·ACL/default ACL/행 hash/sequence/head를 비교한다.
  복원된 역할은 NOLOGIN이며 DB 로그인 비밀번호·Secret·IAM 복구는 이 dump 범위에 포함되지 않는다.

## 검증과 남은 범위

로컬 회귀는 profile 간 URL 거부, query namespace 격리/기존 query 보존,
선택 Secret/v1 고정, 실제 연결 신원·private 접근 누출 시 dump 전 중단,
임의 profile/이미지 거부, 오류 보고서의 비밀 원문 배제와 기존 staging 계약을 확인한다.
실제 PostgreSQL CI에는 전체 migration과 합성 공용 자료 후 demo16테이블/행/head/ACL snapshot,
private sentinel 미포함·원본 보존을 추가한다. 이는 pg_dump/pg_restore 전체 실행과 구분한다.

로컬 백업 회귀18 passed(0.19초), 전체 API 회귀 종료코드0, Ruff app/tests와 strict mypy
app/tests157 source files, diff --check 통과. 로컬 PostgreSQL은 설정 부재로 skip이며 실제 CI 결과는
정확한 PR head에서 별도 확인한다. 로컬 skip을 PostgreSQL 통과로 표현하지 않는다.

아래 실제 실행 결과 이전까지 demo dump/격리 restore는 미실행이었다. 성공하더라도 Cloud Shell home의 1회 복원 리허설이며
예약/오프사이트 백업·장기 보존·RPO/RTO 보장·운영 장애 복구 완료를 뜻하지 않는다.
실행 시간은 작은 합성 데이터와 이미지 준비/프로세스 시간을 포함하므로 DB 성능 지표로 사용하지 않는다.
이후 실제 만료 데이터 정리는 별도 삭제 승인과 보존 검증을 거쳐 진행한다.

면접에서 설명할 핵심은 “dump 파일이 있다”와 “현재 전용 schema의 권한/데이터를 격리된 DB로
복원해 비교했다”의 차이다. 다음 실습은 disposable PG에서 schema/행/ACL 중 하나를 바꾸고
어떤 비교 항목이 실패하는지 확인하는 것이다. 원격 demo 자료를 바꾸어 실습하지 않는다.

## 실제 1회 실행 — 2026-10-23

PR #53 head `bafe62424c2f6511bb8513723b597c6f11b3d869`의 필수 CI5개 성공 후 자체 리뷰 COMMENT/
라벨/병합(main `9a47405`)을 완료했다. CI39885849401: API447 passed/27 skipped38.35초,
PostgreSQL27 passed8.62초(기존 Alembic deprecation5회), browser16+2/container/dependency 성공.
사용자가 demo migration DB Secret v1의 운영 도구 사용과 읽기 전용 dump/격리 restore1회를 승인했다.

Cloud Shell에 위 source archive의 SHA256
`cb3e4053f6adf83e621c4b29d2cbd8b828bd4e391c91cd84e35e1c589f79d907`을 대조해 새 폴더에 안전하게 풀고
frozen 의존성을 설치했다. CA checksum/프로필/CLI, 초기 여유 디스크4.0GiB를 확인했다.
고정 이미지가 없어 Secret 읽기 전에 pull을 마쳤다. 시도 파일을 먼저 만들어 중복 실행을 차단했다.

| 항목 | 실제 결과 |
| --- | --- |
| backup ID | `20261023T015811Z-653f204f` |
| dump | 55,567 bytes, SHA256 `ccee4dd12c7da5c19e41c2b6588f7c576fc1dd312548f9ddb5f8475da2c139bf` |
| schema/head | `groupware_demo` / `f30c9a71b624` |
| 복원 비교 | 16 tables/85 rows, columns/constraints/indexes/ownership ACL/schema ACL/default ACL/rows/sequences/head 일치 |
| 포함 자료 | 규정3/조항10/회사 일정48/방문 공간3/결재1/피드백1/password credential0 |
| 단계 시간 | dump15.29초, restore/비교12.12초; 사전 image pull 시간 제외 |
| 보관/정리 | dump/report0600·개별 폴더0700 독립 재확인, dump 해시 재계산 일치, temporaryContainerRemoved=true |

원본 remote restore/쓰기/삭제, 새 자원/IAM/키, staging/session Secret payload 읽기는 없었다.
추가 Secret 재접근 없이 로컬 report/dump 해시와 권한/건수를 재확인했다.
Supabase 독립 SELECT로 private16테이블64행/head/fingerprint `788dd33280257ec9b390ce8d64b5f3da`,
demo 공간3/결재1/피드백1 불변을 확인했다. 이 fingerprint의 한계는 기존 데이터 보존 문서를 따른다.
덤프는 Cloud Shell `~/jhworks-demo-backups/20261023T015811Z-653f204f/` 안에만 보관하며 Git/채팅에 옮기지 않았다.
안전한 실행 요약은 `~/jhworks-demo-backup-attempt-bafe62424c2f.json`, 전체 검증 보고는 dump 폴더의
`verification.json`이다. 로컬 증거 이미지는 `artifacts/cloud-run/demo-backup-success-20261023.png`다.
이 기록은 장기 백업 서비스나 실제 삭제 후 복구를 검증했다는 뜻이 아니다.
