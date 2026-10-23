# 실제 배포의 세션 서명키 경계 검증

## 실제 검증 완료 — 2026-10-23 19:37:41 KST

PR #59의 exact-head CI5개 성공·자체 리뷰·병합 후, 사용자가 직전 제시한 두 기존 session Secret
v1의 각1회 메모리 검증을 진행하도록 요청했다. 앱 내부 브라우저의 기존 Cloud Shell 인증을 갱신하고 실행했다.
새 IAM 권한·credential·키를 생성하거나 값을 교체하지 않았다.

고정 source `cbe4e90133497df6843f581f8811f49e7162ab11`, 실행 파일 SHA256
`4f58ee072cf7825540bdb2c1e4d50fbbf23883395f1d5efbbab31554241783a6`을 대조했다.
기존 frozen Python 환경에서 source 파일을 실행했으며 서비스 이미지를 새로 빌드/배포한 것이 아니다.
기존 metadata-only 성공 보고서와 source hash를 확인하고 O_EXCL attempt 파일을 만든 뒤
`--verify-keys`를1회 실행했다. 같은 attempt/result가 있으면 자동 반복하지 않는다.

```json
{"status":"passed","secretPayloadsRead":2,"httpRequests":0,"writes":0,"serviceReferencesVerified":2,"distinctKeys":true,"ownSignaturesAccepted":2,"crossSignaturesRejected":2,"stage":"complete","keysVerified":true}
```

도구와 wrapper 모두 exit0이며 관찰 시각은 `2026-10-23T10:37:41.555495+00:00`이다.
검증 직전 두 서비스의 Ready revision/traffic100/runtime 신원/AI off/HS256/각 고정 v1과
서비스 IAM 익명 grant 부재를 다시 확인했다. 두 실제 키의 독립성과 상호 서명 거부를 확인했다.
키·JWT 원문은 결과/파일/셸 명령/채팅으로 출력하지 않았다. DB credential은 읽지 않았다.

보고서는 Cloud Shell `~/jhworks-session-key-check-cbe4e9013349/verified-keys.json`,
시도 기록은 같은 폴더의 `verify-keys-attempt.json`이다. 추가 Secret 접근 없이 기존 결과를 다시 읽고
source hash·보고서0600·폴더0700을 독립 확인했다. 로컬 증거 이미지는
`artifacts/cloud-run/session-key-verified-20261023.png`다.

이 결과는 실제 서비스 간 HTTP 세션 수락/거부를 완료한 증거가 아니다. 이 실행은 API/DB에
접근하지 않았으므로 업무 데이터 fingerprint·만료 UX·현재 DB 보존을 재검증했다고 표현하지 않는다.
다음은 서비스 간 HTTP 경계와 정리 주기·실패/실행 누락 감지 준비다.

아래 내용은 실행 전 설계와 재현 절차다. 반복 실행 허가로 사용하지 않는다.

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
