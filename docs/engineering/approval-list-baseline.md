# 결재 목록 서비스 baseline — M5-01A

페이지네이션·요약 DTO를 바꾸기 전, 현재 `list_approvals` → `approval_read` → `ApprovalListResponse` JSON의 비용을 합성 데이터로 측정한다. HTTP·인증·네트워크·브라우저 렌더링·실행 계획은 아직 측정하지 않으며 M5-01 전체 완료로 표시하지 않는다.

## 격리와 재현

```sh
cd apps/api
# JHWORKS_TEST_POSTGRES_URL은 전용 로컬 테스트 DB를 가리켜야 한다.
uv run python -m app.ops.approval_list_benchmark \
  --counts 100,1000 --repeats 3 --output ../../artifacts/performance/approval-list.json
```

실행기는 `postgresql+psycopg`, loopback host, `jhworks_test` DB·사용자만 허용하고 URL query 옵션을 거부한다. 운영 설정의 `DATABASE_URL`을 연결 대상으로 사용하지 않는다. 별도 비밀번호나 AI 호출·업무 API 요청도 없다. vector extension이 준비된 전용 DB가 필요하며 도구가 extension을 추가하지 않는다.

각 규모마다 `approval_bench_<uuid>` schema에 전체 테이블과 합성 자료를 생성하고 자기 schema만 ANALYZE한다. 성공·실패 시 자기 schema를 제거하며 기존 schema나 데이터는 변경하지 않는다. 프로세스 강제 종료 시 임시 schema가 남을 수 있다. CI의 일회용 PostgreSQL 서비스가 종료되면 해당 DB도 폐기된다. 원격 DB·공개 데모에는 실행하지 않는다.

## 고정 입력과 측정 경계

- fixture `approval-list-v1`, 기준 시각 2026-01-01 UTC. 문서 수100/1000, 최대10000·규모3개·반복5회로 제한한다.
- 작성자3/4·다른 작성자1/4, 모든 문서에 같은 결재자의 이전 반려/현재 대기2개 회차. 비참여자는0건이어야 한다.
- 문서마다 본문960자, 경비 details, 첨부 메타1개를 사용한다. 4개씩 같은 updated_at을 가져 정렬 동률도 포함한다. 현재 목록의 동률 순서는 보장하지 않는다.
- 작성자 mine·결재자 assigned·비참여자 assigned를 순차 측정한다. 각 경우1회 warm-up 뒤3회 측정하고 원시 샘플과 total 중간값을 보관한다.
- 매 샘플은 새 ORM session을 사용하지만 PostgreSQL shared buffer/OS cache는 공유한다. cold-cache·동시성 측정이 아니다.
- 직원 조회를 마친 뒤부터 실제 목록 로딩, mapper, JSON 직렬화를 측정한다. 이 구간의 SQL statement 수, ORM/직렬화/전체 시간, UTF-8 JSON bytes와 반환 행 수를 기록한다.
- connection 준비·직원 조회·HTTP routing/auth·전송 압축·UI 시간은 제외한다. ORM 시간은 DB 서버 실행 시간과 같지 않다.

CI `postgres` job은 기존 PostgreSQL 회귀 뒤 같은 도구를 실행하고 `approval-list-baseline` artifact를 남긴다. report에 source SHA·Python/PostgreSQL 버전·고정 fixture 버전과 반복 조건을 포함하며 접속 URL·세션·키·본문은 넣지 않는다. CI runner의 CPU/캐시 차이를 감안해 서로 다른 실행의 ms만으로 개선을 확정하지 않는다.

## 다음 판단

실제 artifact를 확보한 뒤 크기별 행·SQL·전송량 증가를 확인한다. 이후 동일 조건의 query plan/HTTP/UI 측정과 M5-02의 제한된 목록 계약을 설계한다. 현재 API의 무제한 전체 본문·이력 반환을 이 도구 자체로 개선했다고 주장하지 않는다. 요약 DTO·페이지 상한을 바꿀 때는 목록 UI와 업무 조회 Tool의 전체/일부 결과 의미도 함께 수정해야 한다.

## 첫 실제 PostgreSQL 결과 — 2026-10-26

[CI 실행40205237027](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/40205237027)의 `postgres` job에서 실제 PostgreSQL17.11/Python3.12.15로 실행했다. [원시 report](benchmarks/approval-list-2026-10-26.json)의 source는 GitHub PR 합성 merge `25878c5eb7d60ea9bd004393897e292aeeaed7b6`(PR head `5fd1ca8`)이다. 위 warm-up1/반복3/단일 동시성 조건을 따른다.

| 전체 합성 문서 | 조회자·범위 | 반환 행 | SQL 수 | JSON bytes | ORM+직렬화 중간값 ms |
| --- | --- | --- | --- | --- | --- |
| 100 | 작성자 mine | 75 | 2 | 165172 | 7.17 |
| 100 | 결재자 assigned | 100 | 2 | 220148 | 9.64 |
| 100 | 비참여자 assigned | 0 | 1 | 22 | 1.11 |
| 1000 | 작성자 mine | 750 | 3 | 1651523 | 113.29 |
| 1000 | 결재자 assigned | 1000 | 3 | 2201274 | 168.75 |
| 1000 | 비참여자 assigned | 0 | 1 | 22 | 1.28 |

행·SQL·bytes는 각 경우3회 모두 같았다. 결재자1000건은 압축 전 JSON 약2.20MB이며100건의 약10배다. SQL이 행마다 늘어나는 N+1 양상은 이 조건에서 관찰하지 않았고, select-in loading의 batch 증가로2→3회였다. 본문·첨부 메타·이력 전체를 보내는 응답량은 M5-02 요약 DTO/페이지 상한을 우선 검토할 구체적 근거다. 실제 웹 요청의 지연·압축량·대규모 운영 성능을 측정한 결과는 아니다.

이 측정으로 서비스 baseline만 확인했다. query plan·HTTP/UI 측정과 제한된 목록 계약·개선 후 같은 조건 재측정은 남아 있다.
