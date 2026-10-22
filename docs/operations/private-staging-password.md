# 비공개 검증 계정 비밀번호 교체

2026-10-22 일반 텍스트 확인 칸에 실제 검증 비밀번호가 입력됐음을 사용자가 확인했다.
값 자체는 코드·문서·PR에 기록하지 않는다. 기존 업무 도구는 operator_confirmation에서 중단됐고
비밀번호 입력 대기 중인 재시도도 중단했다. 이 단계까지 앱 로그인·업무 쓰기는 없었다.

## 구현과 대안

staging_password는 기존 private project/revision/IAM/AI-off/max=2 경계와 session pooler,
verify-full·CA pin·승인된 migration secret version 1을 재사용한다. 새 권한·유료 자원을 만들지 않는다.
부서 1·직원 3·credential 3·연차 계정 3과 고정 ID/email/역할/manager, 해당 연도 초기 연차 잔액을
검사한다. 다른 업무 table이 비어 있지 않거나 fixture가 바뀌면 중단한다. count는 예상 건수+1로 제한한다.
기존 계정을 삭제하고 다시 seed하는 방식은 업무 데이터 및 참조 관계를 손상할 수 있어 제외했다.

기본 모드는 read-only preflight다. --apply는 사용자 TTY 숨김 입력·재입력 뒤 단일 transaction에서
전체 업무 table lock과 migration head/fixture 재검사 후 credential hash 3개만 바꾼다.
기존과 같은 비밀번호를 거부하며 각 hash는 별도로 만든다. 중간 실패는 전체 rollback한다.
비밀번호·hash·DB 오류 원문은 출력하지 않는다. 고정 stage/errorType/실제 교체 건수만 출력한다.

--verify-workflow를 추가하면 교체 commit 후 새 값을 메모리에서만 사용해 실제 로그인 및
합성 결재 2건·연차 1일 검증을 이어간다. 이 단계 실패가 이미 commit한 교체를 되돌리지는 않는다.
업무 도구도 일반 텍스트 확인 입력을 없애고 --apply와 숨김 입력을 쓰게 수정했다.
기본 workflow 실행은 service-preflight만 하며 비밀번호를 받거나 업무를 쓰지 않는다.

## 실행

Cloud Shell의 고정·검토된 source checkout에서 실행한다.

```bash
cd apps/api
uv run --frozen python -m app.ops.staging_password \\
  --commit "$RELEASE_SHA" \\
  --ca-file "$HOME/jhworks-supabase-ca.crt"
```

사전 검사 뒤 사용자 직접 실행에만 --apply를 추가한다. 업무까지 검증하려면 --verify-workflow도 추가한다.
NEW private fixture password (hidden, 20+ chars):가 나온 뒤에만 사용자가 기존과 다른 20~128자
비밀번호를 두 번 직접 입력·제출한다. 다른 서비스 비밀번호를 재사용하거나 채팅에 보내지 않는다.
TTY/getpass 숨김 입력이 안 되면 일반 입력으로 fallback하지 않고 중단한다.

## 실제 결과와 한계

Windows cp949 기본 모드 API 250 passed / 23.43초, Ruff, strict mypy 116 files를 통과했다.
동일한 코드 4개를 공식 업로드 UI로 Cloud Shell home에 전송하고 source 445c06a 기반 별도
checkout ~/jhworks-staging-tools/password-recovery-20261022에서 frozen Ruff/mypy와
관련 테스트 20 passed / 11.63초를 확인했다. 실제 DB preflight는 passed / changed=0이었다.

사용자가 직접 실행한 결과 rotatedCredentials=3 / status=passed를 전달했다.
이어진 업무 검증은 initial_author_assigned / ValueError / rotatedCredentials=3에서 실패했다.
이는 교체 성공과 업무 실패가 분리됐다는 결과다. 해당 stage는 결재·휴가 생성 이전이다.
재교체/업무 재실행은 하지 않고 배정 목록 조회의 PostgreSQL 호환성을 다음 작업에서 확인한다.
실제 서버 응답 코드·SQLSTATE는 아직 수집하지 않았으므로 그 원인을 확정한 기록으로 표현하지 않는다.

교체는 기존 비밀번호의 이후 로그인을 차단한다. 기존 stateless session cookie의 개별 폐기는 아니다.
이번 도구가 노출 전에 로그인하지 않았다는 경계와 구분한다. 터미널 화면을 지워도 이전 출력의 모든
사본이 삭제됐다고 주장하지 않는다. 회귀는 재사용/약한 값/fixture 변경 거부·원자성·새 비밀번호로
실제 router 업무 흐름·오류 원문 비노출·기본 no-write·일반 텍스트 입력 없음 검증을 포함한다.

면접에서는 비밀번호 변경과 session 폐기의 차이, atomic credential 교체와 이후 업무 검증의
서로 다른 commit 경계, SQLite 통과와 PostgreSQL 외부 검증의 차이를 이 사례로 설명할 수 있다.
