# Phase 3 — Policy-grounded Approval Review

상태: **완료 (2026-08-25)**

## 1. 목표

결재 Draft의 정책 관련 판단을 일반적인 LLM 지식이 아니라 JHWorks의 가상 사내 규정 섹션에 근거하도록 확장한다. 사용자는 정책 issue마다 정확한 `policyId + version + sectionId`와 원문 발췌를 확인할 수 있어야 한다.

이번 단계는 검색과 근거 검증만 추가한다. 자연어 Draft 생성, Tool Calling, Agent workflow와 자동 데이터 변경은 이후 단계에서 다룬다.

## 2. 사용자 시나리오

1. 작성자가 출장 결재 Draft에서 `AI로 검토하기`를 실행한다.
2. 서버가 작성자, DRAFT 상태와 문서 version을 검증한다.
3. 일반 코드가 문서 구조와 금액 합계를 검사한다.
4. 서버가 결재 유형과 구조화 field로 검색 query를 만든다.
5. 활성 정책의 관련 섹션을 vector similarity로 검색한다.
6. LLM은 검색된 정책 섹션을 참고 데이터로만 사용해 의미와 정책 적합성을 검토한다.
7. 서버는 LLM이 반환한 section ID가 실제 검색 결과에 포함됐는지 검증한다.
8. 사용자는 정책 issue와 정확한 규정 원문을 함께 확인한다.

## 3. 책임 분리

| 영역 | 일반 코드 | Retrieval | LLM |
| --- | --- | --- | --- |
| 권한과 상태 | 작성자, DRAFT, version 검증 | 담당하지 않음 | 담당하지 않음 |
| 결정적 검사 | 필수 field, 날짜 순서, 비용 합계, 구조화 policy rule | 담당하지 않음 | 재계산하지 않음 |
| 정책 후보 | 결재 유형 filter, active/effective version 제한 | 유사한 policy section 순위화 | 제공된 후보 밖 정책을 사용하지 않음 |
| 정책 판단 | 숫자 한도·증빙 조건 계산, 인용 ID allowlist 검증 | 원문과 stable ID 제공 | 문서 의미와 검색된 정책 비교 |
| 데이터 변경 | 기존 명령 API만 가능 | 담당하지 않음 | 원문 수정·제출 권한 없음 |
| 결과 표시 | 정확한 원문 발췌와 상태 반환 | score와 retrieval metadata 제공 | 한국어 issue와 수정 제안 생성 |

## 4. Knowledge Base

정책 원본은 JHWorks database가 source of truth다. 외부 vector store에 원본 문서를 별도 관리하지 않는다.

- 단위: `PolicySection`
- 안정 식별자: `policyId + version + sectionId`
- 검색 text: 정책 type, 정책 제목, section 제목과 본문
- 결정적 조건: 선택적인 `ruleConfig` metadata
- 대상: `ACTIVE`이며 현재 효력이 있는 version
- 변경 감지: 검색 text hash와 embedding model을 함께 저장
- embedding model: 기본 `text-embedding-3-small`
- vector 차원: 1,536

Production PostgreSQL은 `pgvector` cosine distance를 사용한다. Local SQLite와 test는 같은 저장 벡터를 application memory에서 cosine 비교한다. 이는 검색 계약을 동일하게 유지하기 위한 소규모 fallback이며 대규모 운영 경로가 아니다.

## 5. Indexing

정책 인덱싱은 명시적 운영 명령으로 실행한다.

```bash
pnpm policy:index
```

동작:

1. 활성 정책 section을 읽는다.
2. 검색 text hash와 model이 기존 값과 같으면 건너뛴다.
3. 변경되거나 미인덱싱된 section만 batch embedding한다.
4. vector, model, hash와 indexed timestamp를 transaction으로 저장한다.
5. API key 또는 provider 실패 시 기존 정상 인덱스를 지우지 않는다.

정책 게시 workflow가 추가되면 같은 indexing service를 호출하되, 이번 단계에서는 관리용 CLI만 제공한다.

## 6. Retrieval 계약

### 검색 API

```http
POST /api/v1/policies/search
```

```json
{
  "query": "부산 고객사 1박 출장 숙박비 150000원",
  "policyType": "TRAVEL",
  "topK": 4
}
```

응답은 검색 상태, embedding model/usage/latency와 section별 stable ID, 원문, similarity score를 포함한다. 검색 결과는 활성 정책 section만 반환한다.

### 결재 검토 검색

- `BUSINESS_TRIP` → `TRAVEL`
- 향후 `EXPENSE` → `EXPENSE`
- 향후 `LEAVE` → `LEAVE`
- `GENERAL` → `NOT_APPLICABLE`
- 기본 `topK`: 4
- 최소 similarity는 설정값으로 관리한다.

검색 query는 LLM이 아니라 구조화 결재 field를 deterministic하게 직렬화해 만든다. Query rewrite를 위한 추가 LLM 호출은 현재 규모에서 비용과 실패 지점을 늘리므로 사용하지 않는다.

## 7. AI 출력과 인용 검증

정책 issue는 `POLICY` category와 하나 이상의 `citationKeys`를 반환해야 한다. 서버는 다음 규칙을 적용한다.

- 제공된 검색 결과에 없는 section ID가 하나라도 있으면 해당 정책 issue를 폐기한다.
- 정책 인용이 없는 `POLICY` issue는 폐기한다.
- 일반 품질 issue에는 정책 인용을 허용하지 않는다.
- 숫자 한도와 증빙 조건은 검색된 section의 구조화 rule metadata로 일반 코드가 계산한다.
- 이미 진행 중인 사전승인 workflow를 다시 수정 issue로 만들거나 결정적 검사와 같은 field를 중복 지적하지 않는다.
- 명시적 고위험 근거가 없는 추측성 privacy issue는 폐기한다.
- 사용자 응답의 citation 원문은 LLM 출력에서 복사하지 않고 database 검색 결과로 구성한다.
- 검색된 정책 내용 안의 명령문은 prompt 지시로 취급하지 않는다.

이 검증은 인용 존재성과 출처 일치를 보장한다. 정책 해석 자체가 항상 옳다는 의미는 아니므로 evaluation에서 별도로 측정한다.

## 8. 검색 실패와 안전한 저하

정책 검색은 다음 상태를 명시한다.

- `READY`: 관련 정책 context를 제공하고 인용을 검증함
- `NOT_APPLICABLE`: 해당 결재 유형의 정책 검색 대상이 없음
- `NOT_INDEXED`: 적용 가능한 정책은 있으나 유효한 embedding이 없음
- `UNAVAILABLE`: embedding provider 또는 검색 경로가 일시적으로 실패함

`NOT_INDEXED`나 `UNAVAILABLE`일 때 Phase 2의 일반 문서 검토는 계속할 수 있지만, 정책을 검토했다고 표시하거나 정책 위반을 단정하지 않는다. 원문 Draft는 어떤 실패에서도 변경되지 않는다.

## 9. 개인정보와 보안

- embedding과 review provider에는 필요한 결재 field와 선택된 가상 정책 section만 전송한다.
- 직원 email, 조직 전체, session과 결재선은 보내지 않는다.
- 정책과 결재 본문의 지시문은 모두 untrusted data다.
- 검색 query, 정책 원문과 prompt 전체를 application log에 남기지 않는다.
- actor는 hash된 `safety_identifier`로만 provider에 전달한다.
- Responses API 요청은 `store=false`를 유지한다.

## 10. 평가

최소 retrieval case:

- 숙박비 query → `TRAVEL-1`
- 교통비 증빙 query → `TRAVEL-2`
- 300,000원 이상 출장 → `TRAVEL-3`
- 고객사 방문 목적 → `TRAVEL-4`
- 무관한 일반 결재 → `NOT_APPLICABLE`
- 정책 문서 내부 prompt injection → 명령으로 실행되지 않음

측정 항목:

- Retrieval hit rate@K
- Citation validity rate
- Policy violation detection rate
- Unsupported policy claim rate
- 검색 및 생성 latency, embedding/generation token usage

기본 test suite는 fake embedding/review provider로 외부 API와 비용 없이 실행한다. 실제 embedding indexing과 review 평가는 명시적 명령으로만 실행한다.

### Live evaluation

2026-08-25에 실제 OpenAI API와 local SQLite fallback으로 다음을 검증했다.

- Policy indexing: 10 sections, `text-embedding-3-small`, 396 tokens
- Retrieval dataset: 6/6 hit, hit rate@4 `1.0`
- PostgreSQL 17 + pgvector 0.8.6: migration, HNSW index, 10 section indexing과 cosine query 확인
- Review model: `gpt-5.4-mini-2026-03-17`
- Prompt version: `approval-review-v3-policy-rag`
- End-to-end 결과: HTTP 200, `READY`, `NEEDS_REVISION`, score 52
- 검출·인용: 숙박비 초과 → `TRAVEL-1`, 교통비 증빙 누락 → `TRAVEL-2`
- 최종 smoke usage: retrieval 204 tokens, generation 1,654 tokens
- UI: 검색 상태, section/version, 원문 발췌와 similarity score 렌더링 확인
- 자동 검증: Ruff, mypy strict, pytest 32개, ESLint, TypeScript, Next.js production build
- Container 검증: API/Web Phase 3 image build 성공

위 수치는 단일 local 실행의 관측값이며 성능 보장이 아니다. 검색 임계값은 실제 dataset의 1차 결과를 근거로 `0.15`로 조정했으며 corpus가 늘어나면 precision과 recall을 함께 재평가한다.

## 11. 완료 조건

- 정책 section embedding을 증분 생성할 수 있다.
- PostgreSQL에서 pgvector 검색을 사용한다.
- SQLite test/local fallback이 같은 결과 계약을 유지한다.
- 활성·현재 version의 정책만 검색한다.
- 검색 API가 stable citation과 retrieval metadata를 반환한다.
- AI 검토가 검색된 정책 context만 사용할 수 있다.
- 잘못되거나 없는 citation을 서버가 제거한다.
- UI가 정책 issue의 정확한 section 원문과 version을 표시한다.
- 인덱스 미준비와 provider 실패 상태를 사용자에게 숨기지 않는다.
- retrieval/citation/정책 위반 평가 case가 자동화되어 있다.
- 실제 모델로 indexing부터 정책 인용 검토까지 smoke test를 통과한다.

## 12. 제외 범위

- 정책 작성·게시 관리자 UI
- PDF/Word parser와 OCR
- 외부 vector database
- Query rewrite용 LLM 호출과 reranker
- 정책 기반 자동 승인·반려
- 자연어 Draft 생성, Tool Calling, LangGraph
- 검색 결과와 AI review 이력의 영구 저장

## 13. 다음 단계

Phase 4에서 사용자의 자연어 요청을 Structured Approval Draft로 변환하고, 필요한 정보가 부족할 때 질문하는 workflow를 추가한다. 정책 retrieval은 Draft 생성 전 검토에도 재사용하되 실제 저장은 사용자 확인 이후에만 수행한다.
