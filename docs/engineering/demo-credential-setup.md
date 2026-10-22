# 공개 데모 전용 credential 초기 설정

## 문제와 완료 기준

[분리 기반](demo-identity-foundation.md)은 실제 적용됐지만 새 역할은 NOLOGIN, 세 Secret은 비어 있다.
기존 staging helper는 빈 프로젝트 전용이라 기존 서비스가 있는 환경에서 재사용하거나 guard를 해제하지 않는다.
별도 `app.ops.demo_credentials`는 이 정확한 초기 상태만 허용한다. rotation/resume 도구가 아니다.

이 도구의 완료 기준은 새 두 DB 역할의 실제 TLS pooler 인증·private 접근 거부와 Secret version1 세 개 등록이다.
서비스 업데이트·migration·schema seed·IAM 변경·자원 생성·공개 전환·삭제·LLM 호출은 수행하지 않는다.

## 사용자 입력과 부분 실패

TTY와 공식 Seoul pooler/프로젝트 형식·CA 파일·빈 Secret·정확한 v1 읽기 policy를 먼저 검사한다.
TTY가 없으면 getpass의 echo fallback을 허용하지 않고 비밀번호 요청 전에 실패한다.
사용자에게 `SETUP` 같은 일반 확인 문자열을 받지 않는다. 사전 검사 후
`Existing Supabase postgres password (hidden):` 한 번만 요청한다. 이 prompt에서만 사용자가 직접 입력한다.
일반 셸 `$` prompt나 채팅에 비밀번호를 입력하지 않는다.

초기 설정은 다음 순서다.

1. 관리자 DB transaction에서 초기화 advisory lock을 얻고 cloud/DB 사전 조건을 다시 확인한다.
   demo schema가 비어 있고 소유자·NOLOGIN·역할 권한·role search_path·private 접근 거부를 검사한다.
2. 서로 다른 무작위 DB 비밀번호 두 개와 session key를 생성한다. 비밀 값을 argv나 출력에 넣지 않는다.
   libpq로 만든 SCRAM verifier만 ALTER ROLE에 사용하며 이때는 아직 NOLOGIN이다.
3. 새 세 Secret에 stdin으로 값을 전달해 각각 version1을 만들고 ENABLED 상태를 확인한다.
4. 이 과정이 끝나야 같은 DB transaction에서 두 역할을 LOGIN으로 바꾸고 commit한다.
5. runtime transaction pooler(6543)와 migration session pooler(5432)에 새 자격으로 각각 연결한다.
   TLS verify-full/CA 검증, 실제 current_user/current_schema, private schema SELECT 거부를 확인한다.

DB transaction과 GCP 버전 생성은 하나의 분산 transaction이 아니다. GCP 중간 실패 때 DB는 롤백돼
역할이 NOLOGIN으로 남지만 일부 Secret version이 남을 수 있다. commit 결과 불명확/인증 검증 실패라면
부분 상태를 읽어 확인한다. 자동 삭제·덮어쓰기·credential 재생성·즉시 재실행을 하지 않는다.
버전이 하나라도 있거나 역할이 LOGIN이면 새 초기화는 거부한다. statement/lock/idle-in-transaction timeout을
각각 15/5/90초로 설정하지만 전체 외부 호출 시간이나 서비스 가용성 보장은 아니다.

운영자가 명확한 복구 계획을 정해 별도 승인하기 전에는 부분 버전을 지우거나 활성 비밀번호를 교체하지 않는다.
사용자가 관리자 비밀번호를 한 번 입력하는 방식으로 수동 SQL/비밀 복사를 줄였으며, DB password/서명키는
로컬 파일·Git·채팅·셸 history에 저장하지 않는다. 기존 세 Secret은 읽거나 교체하지 않는다.

## 실행 준비와 검증

검증·병합한 full SHA의 source와 archive hash를 고정하고, 공식 Supabase CA와 실제 pooler host를
확인한 뒤 아래 형태로 준비한다. **값 등록/LOGIN 활성화·과금 승인 전 실행하지 않는다.**

```sh
cd <검증된-source>/apps/api
uv run --frozen python -m app.ops.demo_credentials \
  --project jhworks-staging-tykimdream \
  --project-ref uztfgtfvxhpmavybldbh \
  --pooler-host <확인한-공식-Seoul-pooler-host> \
  --ca-file "$HOME/jhworks-supabase-ca.crt" --apply
```

모듈 import나 unit test는 실제 credential을 생성하지 않는다. 일반 테스트는 비TTY/사전 검사 실패 시
prompt 0회, 숨김 입력 한 번, 기존 버전/잘못된 policy 거부, stdin 전달/출력 비노출,
GCP 부분 실패 시 LOGIN 미실행·DB rollback을 검증한다. PG CI는 실제 분리 schema/역할에서 사전 조건을
검사하고 기존 전체 migration·권한 회귀를 계속 실행한다. 외부 pooler 로그인은 아직 사용자 실행 전이다.

서비스 간 실제 HMAC 거부, migration 성공, 빈 demo용 합성 공용 자료 준비와 방문자 흐름은 이후 단계다.
이 helper만 성공했다고 공개 체크포인트 1 전체나 라이브 데모를 완료로 표현하지 않는다.
