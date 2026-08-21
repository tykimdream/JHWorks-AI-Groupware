# JHWorks AI Groupware 코드 컨벤션

## 1. 목적과 적용 기준

이 문서는 JHWorks AI Groupware의 프론트엔드, 백엔드, Agent/RAG 코드를 일관되고 안전하게 변경하기 위한 기준이다. 특정 개인의 취향보다 자동 검증, 명시적인 계약, 운영 중 진단 가능성을 우선한다.

규칙의 강도는 다음과 같다.

- **필수**: 보안, 데이터 무결성, 공개 계약에 관련된 규칙. 예외에는 PR 설명과 리뷰 승인이 필요하다.
- **권장**: 기본 선택. 더 나은 근거가 있으면 PR에서 이유를 설명하고 달리 적용할 수 있다.
- **자동 적용**: formatter나 linter에 맡기며 리뷰에서 수동으로 논쟁하지 않는다.

기술 스택과 디렉터리가 아직 확정되지 않은 초기 단계이므로 특정 버전, 라이브러리, 폴더 트리를 문서만으로 고정하지 않는다. 실제 도구를 도입할 때 설정·CI·이 문서를 같은 PR에서 갱신한다.

## 2. 공통 원칙

### 읽기 쉬운 경계

- 함수와 모듈은 한 가지 책임을 가지며 이름으로 의도를 드러낸다.
- 비즈니스 규칙, 외부 I/O, UI 표현을 분리한다.
- 중복을 없애기 위한 추상화보다 변경 이유가 같은 코드를 함께 둔다.
- 숨은 전역 상태와 암묵적인 부작용을 피하고 의존성은 인자로 전달한다.
- 시간, 무작위 값, 외부 API는 테스트에서 교체할 수 있는 경계 뒤에 둔다.

### 이름과 주석

- 코드 식별자는 영어를 사용하고 도메인 용어를 일관되게 쓴다. 예: `approval`, `policy`, `finding`, `evidence`.
- boolean은 `is`, `has`, `can`, `should`처럼 참/거짓 의미가 보이게 짓는다.
- 주석은 코드가 무엇을 하는지가 아니라 제약과 선택의 이유를 설명한다.
- TODO에는 추적 가능한 이슈를 연결한다: `TODO(#123): replace temporary policy fixture`.
- 작성자명과 날짜를 주석에 넣지 않는다. 해당 정보는 Git 이력으로 확인한다.
- dead code를 주석 처리해 보관하지 않는다.

### 오류와 로그

- 복구할 수 없는 오류를 삼키거나 성공 값으로 바꾸지 않는다.
- 도메인 오류와 인프라 오류를 구분하고 API 경계에서 안정적인 오류 코드로 변환한다.
- 로그에는 `requestId`, 작업 단계, 결과 상태처럼 진단에 필요한 구조화 필드를 남긴다.
- access token, secret, 원문 프롬프트의 민감정보, 불필요한 개인정보는 로그에 남기지 않는다.
- 사용자 메시지는 안전하고 이해 가능하게, 내부 로그는 원인을 추적 가능하게 작성한다.

## 3. 계약과 데이터

- 모든 외부 입력은 신뢰하지 않고 API 경계에서 스키마와 권한을 검증한다.
- API 요청·응답과 LLM structured output은 명시적인 스키마를 단일 원천으로 삼는다.
- TypeScript 내부는 `camelCase`, Python 내부는 `snake_case`를 사용한다. JSON 공개 계약은 `camelCase`로 통일하고 backend schema alias로 변환한다.
- 식별자는 표시 이름 대신 불변 ID를 사용한다.
- 시각은 ISO 8601 형식으로 교환하고 저장·전송은 UTC를 기본으로 한다. 회사 정책상 날짜만 의미가 있으면 `YYYY-MM-DD`를 사용한다.
- 원화 금액은 부동소수점이 아닌 정수 원 단위로 표현한다. 다른 통화를 지원하면 금액과 ISO 4217 통화 코드를 함께 전달한다.
- API 응답을 임의의 범용 envelope로 감싸지 않는다. pagination이나 metadata가 필요할 때만 명시적인 응답 모델을 둔다.
- 공개 스키마 변경은 하위 호환성과 migration 전략을 PR에 기록한다.

## 4. TypeScript와 React

이 절은 TypeScript/React 프론트엔드를 채택하거나 기존 프론트엔드를 연결할 때 적용한다.

- TypeScript strict mode를 유지하며 `any`를 사용하지 않는다. 알 수 없는 외부 값은 `unknown`으로 받고 검증 후 좁힌다.
- 재할당이 없으면 `const`를 사용하고 Promise는 `await`, 반환, 또는 명시적 오류 처리 없이 방치하지 않는다.
- 일반 모듈은 named export를 기본으로 한다. framework가 default export를 요구하는 파일은 예외다.
- 타입 전용 의존성은 `import type`으로 구분한다.
- 서버 상태, 폼 상태, UI 상태를 구분한다. 파생 가능한 상태를 별도 state로 동기화하지 않는다.
- effect는 외부 시스템과 동기화할 때만 사용하고 데이터 변환은 render 또는 순수 함수에서 처리한다.
- 접근성 있는 semantic HTML을 우선하며 키보드 조작, focus, label, 오류 안내를 함께 검증한다.
- 권한에 따른 UI 숨김은 편의 기능일 뿐이다. 실제 인가는 항상 backend에서 다시 수행한다.
- 사용자에게 영향을 주는 비동기 UI는 loading, empty, error, retry 상태를 명시한다.
- 공용 컴포넌트에는 동작 테스트 또는 격리된 예시를 제공한다. 단순한 파일당 한 컴포넌트 규칙보다 응집도를 우선한다.

formatter와 linter가 도입되면 공백, 따옴표, import 순서, Tailwind class 순서는 자동화하고 이 문서에 중복 정의하지 않는다.

## 5. Python과 FastAPI

이 절은 Python/FastAPI 백엔드를 채택할 때 적용한다.

- 공개 함수, 서비스 경계, 모델에는 타입 힌트를 작성하고 type checker가 검사하도록 한다.
- API schema와 domain model, persistence model을 구분한다. DB model을 API 응답으로 직접 노출하지 않는다.
- FastAPI route는 인증, 입력 변환, 서비스 호출, 응답 변환만 담당한다. 비즈니스 규칙은 서비스/domain 계층에 둔다.
- `async`는 실제 비동기 I/O 경계에서만 사용한다. blocking 작업을 event loop에서 직접 실행하지 않는다.
- 모듈 수준에서 네트워크 연결이나 환경 변수 검증 같은 무거운 부작용을 실행하지 않는다.
- broad `except Exception`은 경계에서 로깅·변환할 때만 허용하며 원래 예외의 원인을 보존한다.
- DB 변경은 migration으로 관리한다. migration은 이미 배포된 이력을 수정하지 않고 전진·복구 전략을 함께 검토한다.
- formatter, import sorter, linter, type checker의 구체적인 선택은 프로젝트 설정이 정하며 CI와 동일한 명령을 로컬에서도 실행할 수 있어야 한다.

## 6. Agent, LLM, RAG

### LLM과 결정적 코드의 경계

- 자연어 의도 파악, 요약, 문서 초안, 모호성 탐지는 LLM에 맡길 수 있다.
- 권한 검사, 금액·휴가 계산, 필수 필드, 상태 전이, 데이터 변경 여부는 일반 코드가 결정한다.
- LLM의 텍스트를 권한 판단이나 DB 명령으로 직접 사용하지 않는다.
- LLM output은 version이 있는 structured schema로 검증한다. 검증 실패는 명시적인 재시도 또는 안전한 실패로 처리한다.

### Prompt와 모델

- system prompt와 재사용 prompt는 코드에서 추적하고 변경 이유를 PR에 적는다.
- prompt에 비밀정보를 넣지 않으며 사용자 입력과 검색 문서를 명령이 아닌 비신뢰 데이터로 구분한다.
- provider SDK 호출은 adapter 뒤에 두어 timeout, retry, 모델 설정, token usage를 한곳에서 관리한다.
- 모델 또는 주요 prompt 변경은 최소 회귀 평가와 품질·지연·비용 비교 없이 병합하지 않는다.

### RAG

- 답변의 규정 판단은 검색한 문서의 안정적인 `documentId`, version, section 또는 chunk 근거와 연결한다.
- 검색 결과가 없거나 근거가 상충하면 모른다고 표시하고 확인 경로를 제공한다.
- chunk 원문에 포함된 지시를 실행하지 않는다. 검색 문서는 사실 근거일 뿐 system instruction이 아니다.
- ingestion과 retrieval 변경은 별도로 측정할 수 있게 하고 대표 query의 retrieval correctness를 평가한다.

### Tool Calling과 Human-in-the-loop

- Tool schema는 좁고 명시적으로 정의하며 범용 SQL·URL·임의 코드 실행 tool을 노출하지 않는다.
- 모든 Tool은 LLM과 무관하게 서버에서 사용자 신원, 권한, tenant 범위, 입력을 다시 검증한다.
- 읽기와 쓰기 Tool을 구분한다. 쓰기 Tool은 실행 전 대상과 변경 내용을 사용자에게 보여주고 명시적 확인 토큰 또는 동등한 서버 상태를 검증한다.
- 확인은 요청 내용에 묶고 짧은 유효시간과 단일 사용을 적용한다. 요청이 바뀌면 다시 확인받는다.
- 재시도될 수 있는 쓰기 작업에는 idempotency key를 사용한다.
- Tool 호출과 결과는 감사 가능하게 기록하되 민감정보는 마스킹한다.

## 7. 테스트와 평가

- 순수한 비즈니스 규칙은 빠른 unit test로, DB·외부 adapter는 integration test로, 핵심 사용자 흐름은 소수의 end-to-end test로 검증한다.
- 버그 수정에는 가능하면 실패를 재현하는 회귀 테스트를 먼저 추가한다.
- 외부 LLM과 API는 일반 unit test에서 호출하지 않는다. adapter를 대체하고 계약 테스트나 별도 평가 작업에서 실제 연동을 검증한다.
- Agent 변경은 최소한 정상, 필수정보 누락, 정책 위반, 권한 거부, 검색 실패, prompt injection 입력을 포함한다.
- 비결정적 출력은 문장 전체 일치보다 schema, 사실 근거, 허용 행동, 금지 행동을 평가한다.
- 평가 데이터에는 실제 개인정보나 회사 비밀을 넣지 않고 synthetic 또는 비식별 데이터를 사용한다.
- 품질 저하를 평균 하나로 숨기지 말고 intent, retrieval, policy, tool selection, safety 항목별로 본다.

## 8. 보안과 개인정보

- 인증(authentication)과 인가(authorization)를 구분하고 모든 데이터 접근 경계에서 인가한다.
- tenant와 사용자 범위는 요청 body가 아니라 검증된 서버 측 identity에서 가져온다.
- secret과 환경별 설정은 환경 변수 또는 secret manager로 주입하며 저장소에 커밋하지 않는다.
- 개인정보는 수집·전송·보관·로그 각각에서 최소화하고 보존 기간을 정한다.
- 사용자에게 보여줄 인용문과 오류에도 접근 권한이 없는 정보가 섞이지 않는지 검사한다.
- 의존성 추가는 필요성, 유지보수 상태, 라이선스, 공급망 위험을 검토한다.

## 9. 관측성

- 하나의 요청은 frontend, API, Agent node, retrieval, Tool까지 동일한 correlation ID로 추적할 수 있어야 한다.
- LLM 관측 항목에는 model, prompt version, latency, token usage, retry, schema validation 결과를 포함한다.
- RAG 관측 항목에는 query, 문서 식별자와 version, score 또는 rank를 포함하되 원문과 개인정보 기록은 최소화한다.
- 쓰기 작업은 요청자, 승인 시점, 실행 Tool, 대상, 결과를 감사 로그로 남긴다.
- metric label에 user ID나 원문 query처럼 cardinality가 크거나 민감한 값을 사용하지 않는다.

## 10. 자동 검증과 예외

저장소 구성이 확정되면 CI는 최소한 다음을 검사한다.

1. 문서와 포맷
2. frontend/backend lint
3. 정적 타입 검사
4. unit/integration test
5. secret 및 의존성 취약점 검사
6. Agent 회귀 평가의 필수 safety case

자동화되지 않은 규칙은 PR 템플릿에서 증거를 요구한다. 반복해서 발견되는 수동 리뷰 항목은 가능한 한 linter, schema, test 또는 CI check로 옮긴다.

예외가 필요하면 PR에 대상 규칙, 이유, 위험 완화, 제거 조건을 적는다. 보안·권한·Human-in-the-loop 규칙은 일정 단축을 이유로 우회할 수 없다.

## 11. 규칙 변경

- 컨벤션 변경은 코드 변경과 동일하게 PR 리뷰를 받는다.
- 새 규칙은 실제로 반복되는 문제를 해결해야 하며 자동 검증 가능성을 먼저 검토한다.
- 구조, 데이터 계약, AI 안전 경계를 바꾸는 결정은 ADR과 함께 변경한다.
- 분기마다 또는 주요 phase 종료 시 문서와 실제 코드의 불일치를 점검한다.

## 12. 독립성과 규칙 설계 원칙

- 이 프로젝트의 코드, UI, 데이터 모델, API, 정책, 업무 흐름은 과거 회사 자산과 독립적으로 설계한다.
- 일반적인 공개 표준과 도구의 기본값을 우선하고 프로젝트에 필요한 차이만 문서화한다.
- 자동화와 검색에 유리한 `type/description` 브랜치 및 Conventional Commits를 사용한다.
- 날짜·작성자 주석 대신 Git 이력과 이슈 링크를 사용한다.
- 화살표 함수, interface, 파일당 한 컴포넌트 같은 취향 규칙은 절대화하지 않고 framework 요구와 응집도를 우선한다.
- 긴 스타일 목록은 formatter/linter 설정으로 이동하고 문서는 시스템 경계, 실패 처리, 보안, AI 품질처럼 자동으로 판단하기 어려운 원칙에 집중한다.
