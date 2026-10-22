# 비공개 staging의 합성 업무 검증 준비

현재 정상 release는 빈 업무 DB에서 HTTP 4개를 검증했다. 로그인·일반 결재·휴가·비참여자 거부를
검증하려면 실제 계정이 필요하다. 로컬 공개 seed는 그대로 사용하지 않는다.
이 문서의 도구 추가와 실제 계정 생성은 별개다. 실제 인증정보 설정은 사용자 확인·직접 입력 후 진행한다.

## 범위와 사전 조건

- 전용 GCP project/name/number, private IAM, invoker check, AI=false, service max=2와
  명시한 full SHA의 Ready revision/100% traffic을 확인한다. 다른 project/서비스를 받지 않는다.
- Cloud Shell home의 실제 restore-verified archive와 report/head/SHA256이 일치해야 한다.
- 승인된 migration secret version 1만 메모리로 읽고 session pooler/역할/verify-full/CA pin을 확인한다.
- read-only transaction에서 migration head와 업무 10개 table의 빈 상태를 확인한다.
- 작성자/결재자/비참여자 3명과 부서 1개·연차 계정 3개만 만든다. 관리자/DB role/IAM/Secret은 만들지 않는다.
  세 계정은 private 검증용 하나의 사용자 설정 비밀번호를 사용하며 각 Argon2 hash는 별도로 생성한다.
- 실제 생성은 단일 transaction에서 table lock 후 빈 상태를 재검사한다. lock 5초·statement 15초 제한,
  중간 실패 시 전체 rollback, 재실행 시 기존 데이터를 덮어쓰거나 삭제하지 않는다.

## 사용자 실행 절차

먼저 현재 배포 SHA와 실제 backup reference로 **기본 사전 검사 모드**를 실행한다.
Cloud Shell의 별도 source checkout에서 frozen API dependencies를 사용한다. source/venv는 사용자
home의 전용 staging 도구 directory에 두며 채팅에 credential을 보내거나 Secret 값을 복사하지 않는다.

```bash
cd apps/api
uv run python -m app.ops.staging_fixture \
  --commit "$RELEASE_SHA" \
  --backup-reference "$VERIFIED_BACKUP_REFERENCE" \
  --ca-file "$HOME/jhworks-supabase-ca.crt"
```

사전 검사 통과와 사용자 승인 뒤에만 같은 명령에 `--apply`를 추가한다. 사용자가 직접
`CREATE PRIVATE FIXTURE`를 입력하고 password manager에서 만든 별도 20~128자 비밀번호를
숨김 prompt에 두 번 입력·제출한다. GCP/Supabase/다른 서비스 비밀번호를 재사용하지 않는다.
도구는 interactive TTY가 아니거나 getpass가 echo 모드로 fallback하면 중단한다.
비밀번호를 command argument·환경변수·Git·로그·채팅으로 전달하지 않는다.

생성될 주소는 `staging.author@jhworks.test`, `staging.approver@jhworks.test`,
`staging.unrelated@jhworks.test`다. 실제 사람·조직 정보가 아니다. 이후 API 검증은 Google ID token의
ingress 인증과 앱 session cookie 인증을 함께 유지하고 실제 업무 command endpoint를 사용한다.
fixture는 결재/휴가 상태를 SQL로 미리 완성하거나 AI 확인 절차를 우회하지 않는다.

## 검증과 한계

로컬 회귀는 세 합성 계정/manager 연결/별도 hash, 기본 비밀번호 차단, 재실행 거부,
중간 credential 생성 실패의 전체 rollback, archive 변조, public IAM/다른 revision/AI 활성 거부를 검증한다.
관련 테스트 10개와 전체 API **230 passed / 18.03초**(cp949 기본 모드),
Ruff app/tests/alembic, strict mypy app/tests 112 source files를 통과했다.
실패 결과는 고정된 stage/errorType만 남기며 DB 원문·비밀번호·password hash를 출력하지 않는다.
이것은 SQLite/대역 GCP 단위 검증이며 실제 Supabase fixture 생성·동시 쓰기 검증 완료를 의미하지 않는다.

private 검증 계정을 공개 demo에 그대로 재사용하지 않는다. 공개 전 세션 격리·호출 제한·기존 검증 계정
처리를 별도 확인한다. 예약 초기화/계정 만료/보존 정책은 아직 구현하지 않았다.
