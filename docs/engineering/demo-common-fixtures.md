# 전용 데모의 합성 공용 자료

## 문제와 선택

전용 schema로 실제 전환한 뒤 방문자 결재/피드백은 통과했지만 정책/공용 일정은 비어 있다.
기존 로컬 seed에는 공개 기본 비밀번호·고정 직원과 조직이 함께 있으므로 원격 guard를 해제하거나
그 데이터를 private schema에서 복사하지 않는다. visitor 프로비저닝과 분리된 작은 초기 SQL을 사용한다.

`supabase-demo-common.sql`은 전용 `groupware_demo`에 합성 규정3·조항10·회사 공통 일정48개만 넣는다.
직원·조직·로그인 credential·leave account·결재·방문 공간·피드백을 생성/수정하지 않는다.
기존 runtime/backend 코드를 바꾸지 않으므로 이 자료 등록만을 위해 이미지를 재빌드/재배포하지 않는다.
기존 Free DB의 작은 합성 행이며 새 유료 자원·IAM·키·외부 AI/embedding 호출·공개 전환은 없다.

## 입력과 경계

- 출장/경비/연차 규정은 프로젝트의 기존 합성 규칙과 같은 금액/조건을 한국어 예시로 적었다.
  실제 회사 규정·법적 휴가 기준이 아니며 제목과 일정 설명에 체험/합성임을 표시한다.
- 정책은 ACTIVE/demo-1.0, 규칙 JSON과 정렬 조항의 content hash를 저장한다. embedding은 NULL이다.
  규정 등록을 RAG 인덱싱 또는 실제 LLM 검증 완료로 표현하지 않는다. AI off는 유지한다.
- DB current_date의 현재·다음 연도 24개월에 월2개 합성 일정: 첫 수요일 휴무/BLOCKED와
  둘째 목요일 타운홀/CAUTION. 실제 법정 공휴일이 아니다. COMPANY scope이며 직원/부서/결재 참조는 없다.
  이 초기 자료의 연도 창이 끝나기 전에 새 자료 갱신을 별도 검토한다. 예약 갱신은 구현하지 않는다.
- 기존 schema 소유자/고정 migration head·LOGIN 역할2개·private 접근 거부·password credential0을
  확인하고, postgres 운영자 또는 disposable jhworks_test DB/user에서만 실행한다.
- 초기화 lock을 즉시 얻지 못하거나 공통 정책/조항/COMPANY 일정이 이미 있으면 실패한다.
  기존 자료를 채택/덮어쓰기/삭제하지 않는다. DEPARTMENT/EMPLOYEE 일정은 보존한다.

하나의 DO 문 안에서 모두 실행한다. 후반 calendar INSERT가 실패해도 앞서 넣은 정책/조항 행이
같은 transaction에서 rollback된다. PostgreSQL sequence 번호의 연속성을 보장하는 것은 아니다.
같은 초기 SQL의 재실행은 변경0으로 실패하며, 성공한 자료를 갱신하려면 별도 변경 절차가 필요하다.
기존 로컬 seed의 원격 DB 차단은 그대로다.

## 검증과 실제 적용 gate

SQL UTF-8/LF SHA256: `27f6faccd43972850fcf231982eaceeb85923cef7f3bf9ea30675021298230b4`.
먼저 PR의 실제 PostgreSQL CI를 통과하고 리뷰·병합한다. 소유자/role/대상 schema·기존 공용 자료0과
기존 데이터 기준값을 다시 확인한 뒤 운영자 SQL Editor에서 이 고정 SQL을 실행한다.
이는 schema 권한/credential 변경이 아니며 private 원문을 읽어 옮기는 작업도 아니다.
아래 실제 적용 결과 이전까지는 원격 DML을 실행하지 않았다.

테스트는 loopback의 disposable jhworks_test DB/user만 허용하는 기존 PG fixture 안에서
bootstrap→실제 전체 migration→LOGIN 상태를 준비한다. 정상 건수/정책 hash/조항 순서·embedding NULL,
24개월48개 scope/참조, 기존 부서 일정·private sentinel 보존, 재실행 거부, runtime의 초기화 거부,
private 접근 누출 시 거부, 후반 INSERT 제약 실패 때 정책/조항 rollback을 검증한다.
fixture의 역할/schema/DDL/DML은 outer transaction으로 rollback하며 기존 대상을 삭제/채택하지 않는다.
로컬 Docker daemon이 없어 PG 실행은 CI에 맡기며 로컬 skip을 통과로 보고하지 않는다.

실제 적용 후에는 private fingerprint/head와 기존 방문 공간2/결재1/피드백1 보존을 비교한다.
새 방문자가 정책 목록과 현재 날짜 창의 공통 일정을 읽는 실제 HTTP를 확인한다.
이 검증도 custom domain 브라우저·접근성·성능·실제 AI 검증과 구분한다.

## 실제 적용 결과 — 2026-10-23

PR #52 head `7dd266295aaa36f5b48f96c4a91188ed3f002c6b`의 CI
[39881061284](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39881061284)
5개 성공 후 자체 리뷰 COMMENT/라벨/병합(main `c990cec`)을 완료했다. 독립적인 사람의 승인과 구분한다.
API441 passed/26 skipped(38.43초), 실제 PostgreSQL26 passed(6.26초), browser16+public2,
container-smoke/dependency-review 성공이다. PG의 기존 Alembic path_separator deprecation 경고4개는 남았다.

Supabase SQL Editor에서 기존 대상/빈 공통 자료/LOGIN2/credential0을 확인하고 위 SHA의 SQL을 1회
실행했다. Success 후 별도 SELECT로 규정3/조항10/COMPANY 일정48, credential0을 확인했다.
기존 공간2/결재1/피드백1은 자료 등록으로 바뀌지 않았다.

전용 revision `jhworks-demo-75d5e8a98fb2-3c51785fafdb`에 기존 operator ID token으로 실제 HTTP7개를
검증했다. 토큰/쿠키는 프로세스 메모리에만 사용하고 원문 응답/credential을 기록하지 않았다.
configuration200/AI=false → demo start200 → policies200(3종/10조항/demo-1.0/정렬 content hash 일치)
→ 2026-11 attendance overview200(COMPANY2개) → leave availability200(잔여15/READY,
11월4일 합성 휴무 BLOCKED·선택 불가, 11월12일 타운홀 CAUTION·선택 가능)
→ logout200 → policies401을 확인했다. 이 과정에서 새 공간1개를 추가했다.
안전한 결과 파일은 Cloud Shell의 고정 rollout 폴더 `common-http-result.json`에 보관한다.

최종 독립 SQL 재조회: 공간3/결재1/피드백1, 공통3/10/48, credential0, LOGIN2.
private16테이블64행/head `f30c9a71b624`/데이터 fingerprint `788dd33280257ec9b390ce8d64b5f3da`
모두 이전과 같다. fingerprint는 작은 합성 데이터의 행 변경 탐지이며 전체 DB/ACL/sequence 복구 증거가 아니다.
로컬 증거 이미지는 `artifacts/cloud-run/demo-common-final-counts-20261023.png`와
`demo-common-final-preservation-20261023.png`이며 Git에는 dump/원문 업무 행을 넣지 않는다.
새 이미지 배포/유료 자원/IAM/credential 변경/실제 삭제/AI/공개 전환은 없었다.
