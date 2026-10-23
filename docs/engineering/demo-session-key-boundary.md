# 실제 배포의 세션 서명키 경계 검증 준비

## 문제와 범위

서로 다른 Secret 이름/version 참조만으로 저장된 키 값도 다르다고 단정할 수 없다.
`app.ops.session_key_boundary`는 두 실제 서비스의 현재 Ready revision/traffic100, runtime 신원,
AI off, HS256과 고정된 session Secret v1 참조, 서비스 IAM의 익명 grant 부재를 먼저 확인한다.
기본 실행은 이 metadata만 읽으며 Secret payload를 읽지 않는다.

`--verify-keys`를 명시하면 기존 operator 인증으로 `jhworks-session-secret` v1과
`jhworks-demo-session-secret` v1 두 개만 프로세스 메모리로 읽는다. DB credential은 읽지 않는다.
독립된 두 키로 60초짜리 합성 session JWT를 각각 만들고 자체 서명 수락2/상대 서명 거부2를 확인한다.
subject는 실제 직원이 아닌 무작위 합성 probe ID다. 키/token/원문 예외를 출력하거나 저장하지 않는다.
Secret 값의 공백·개행을 제거하거나 바꾸지 않으며 키가 같거나32자 미만이면 실패한다.

이 검사는 실제 저장된 키의 독립성과 HS256 상호 서명 거부를 증명한다. live API에 token을
전송하거나 DB 직원을 조회하지 않으므로 서비스 간 HTTP 인증 거부·업무 권한·만료 UX 검증을 대신하지 않는다.
IAM·Secret·서비스 설정이나 데이터 변경, 새 key·credential 발급, Job 실행·LLM 호출은 없다.

## 실행과 승인 검토

리뷰·CI를 통과한 full source SHA와 archive hash를 대조한 Cloud Shell source에서 실행한다.

```sh
cd <검증된-source>/apps/api
uv run --frozen python -m app.ops.session_key_boundary
```

기본 metadata 결과를 확인한 뒤, 두 session Secret v1의 **운영 검증 도구 사용 범위**를 확인하고 실행한다.
이는 새로운 Secret IAM 권한을 만드는 작업이 아니다. 이 문서를 작성한 시점에는 실제 payload 검증을 실행하지 않았다.

```sh
uv run --frozen python -m app.ops.session_key_boundary --verify-keys
```

성공 결과는 `serviceReferencesVerified=2`, `secretPayloadsRead=2`, `distinctKeys=true`,
`ownSignaturesAccepted=2`, `crossSignaturesRejected=2`, `httpRequests=0`, `writes=0`이다.
metadata-only 성공은 `keysVerified=false`이고 실제 키 검증 성공으로 표시하지 않는다.
실패하면 stage/errorType과 이미 읽은 payload 개수만 남긴다. 자동 재시도·값 교체·복구 변경을 하지 않는다.

## 회귀

기본 metadata-only, 잘못된 runtime/Secret version/traffic/AI/public IAM 시 Secret 읽기0,
동일 키·짧은 키 거부, opt-in 이후에만 payload2회 읽기와 token/키/예외 원문 비노출을 검사한다.
합성 키 단위 테스트를 실제 원격 Secret 검증으로 표현하지 않는다.

로컬 전체 API462 passed/29 skipped(20.30초), Ruff app/tests/alembic,
strict mypy app/tests159 source files가 통과했다. 새 합성 검증15개를 포함하며
로컬 PostgreSQL은 미설정으로 skip했다. 실제 원격 key payload 검증은 아직 하지 않았다.
