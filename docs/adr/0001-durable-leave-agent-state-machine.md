# ADR-0001 — 휴가 Agent의 durable application state machine

- 상태: Accepted
- 날짜: 2026-08-25
- 범위: Checkpoint 15 휴가 제출 중단·재개 workflow

## Context

휴가 상담은 여러 번의 후속 질문, Draft exact preview 확인, Draft 생성, 별도의 제출 preview 확인과 제출을
순서대로 처리한다. provider 또는 submit Tool 실패 뒤에도 동일 지점에서 재시도해야 하며, 취소·만료·stale은
Approval과 LeaveAccount를 변경하지 않아야 한다. 제출은 기존 Approval, ApprovalLine, LeaveAccount와
WorkCalendarEvent 규칙을 한 transaction에서 검증하고 변경한다.

LangGraph의 [interrupt](https://docs.langchain.com/oss/python/langgraph/interrupts)와
[persistence](https://docs.langchain.com/oss/python/langgraph/persistence)를 검토했다. interrupt를 재개하면
해당 node가 처음부터 다시 실행되므로 interrupt 이전 side effect는 idempotent해야 한다. production
durability에는 checkpointer와 stable thread ID도 필요하다. 이는 유용한 기능이지만 현재처럼 분기가 작고 Tool
순서가 고정된 workflow에서는 별도 checkpoint store가 application DB의 상태와 중복된다.

## Decision

SQLAlchemy의 `leave_agent_runs`를 단일 workflow source of truth로 사용한다.

- 명시적인 enum transition과 actor-scoped route만 제공한다.
- 상담 결과, Draft preview와 제출 preview를 durable JSON snapshot으로 보존한다.
- signed confirmation은 actor, run, preview와 현재 domain version/fingerprint에 결합한다.
- submit service의 기존 DB transaction이 최종 authorization과 stale 검사를 다시 수행한다.
- 성공 replay는 이미 저장된 Draft 또는 PENDING Approval로 수렴한다.
- transient failure는 `FAILED`와 retry count를 저장하고 동일 interrupt 입력으로 재개한다.
- trace에는 transition과 정제된 result code만 저장한다.

LangGraph는 현재 dependency에 추가하지 않는다.

## Consequences

workflow와 업무 상태가 같은 database와 transaction discipline을 사용해 장애 분석과 원자성 경계가 단순하다.
반면 임의의 동적 graph, 병렬 Tool fan-out, 장기간 human task scheduling을 직접 제공하지 않는다. 현재 요구에는
그 기능이 없으며 명시적 service와 integration test가 더 작은 구조다.

## Reconsider when

다음 중 하나가 실제 요구가 되면 LangGraph 또는 다른 workflow engine을 다시 비교한다.

- LLM이 다음 Tool을 동적으로 선택하는 반복 loop가 여러 단계에 걸쳐 durable해야 하는 경우
- 병렬 branch, subgraph, 장기 scheduler와 외부 worker handoff가 필요한 경우
- application DB 밖의 다수 시스템을 보상 transaction으로 orchestration해야 하는 경우
- framework checkpoint inspection과 time-travel debugging이 운영 요구가 되는 경우

재검토 시에도 Agent를 security boundary로 사용하지 않고 모든 Tool의 actor authorization, schema validation,
idempotency와 domain transaction 검증을 유지한다.
