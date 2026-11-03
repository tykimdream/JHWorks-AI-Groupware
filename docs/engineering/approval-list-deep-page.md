# 결재 요약 목록 뒤쪽 페이지 측정 — 2026-11-03

`8c23701`에 이 계측 변경을 적용한 작업 트리에서 기존 `approval-list-v1` 합성 fixture 1,000건을 PostgreSQL 17의 전용 loopback DB에서 측정했다. 작성자 750건, 결재자 1,000건, 비참여자 0건을 같은 권한 조건으로 조회했다. 각각 첫 20건(offset 0)과 401번째부터 20건(offset 400)을 비교한다. 각각 별도 warm-up 1회·새 ORM session으로 3회 실행하고, 그 뒤 동일 쿼리의 `EXPLAIN ANALYZE`를 한 번 더 수집했다.

```sh
cd apps/api
# vector가 준비된 전용 loopback jhworks_test DB만 사용
uv run --frozen python -m app.ops.approval_list_benchmark \
  --counts 1000 --output ../../artifacts/performance/approval-deep-page.json
```

| 대상 | 전체 / 반환 | 첫 페이지 ORM·직렬화 중앙값 | offset 400 중앙값 | offset 400 페이지 SQL 실행 시간 |
| --- | --- | ---: | ---: | ---: |
| 작성자 | 750 / 20 | 2.99ms | 2.85ms | 0.483ms |
| 결재자 | 1,000 / 20 | 4.63ms | 4.55ms | 1.519ms |
| 비참여자 | 0 / 0 | 1.47ms | 1.43ms | 0.011ms |

[원시 샘플 및 계획](benchmarks/approval-deep-page-2026-11-03.json)은 SQL 조건과 인자를 제거한다. 두 페이지 모두 전체 count 쿼리를 별도로 실행한다. 이 규모의 단일 실행에서는 뒤쪽 페이지 중앙값이 더 크지 않았으나, 3개 샘플·공유 warm cache의 잡음이 있으므로 비용이 같거나 개선됐다고 단정하지 않는다. HTTP·브라우저·동시 부하·운영 데이터·public workspace는 포함하지 않으며 offset 400 한 지점이 최대 offset 10,000의 성능을 대표하지 않는다. 페이지 사이 문서 수정에 따른 중복·누락 가능성도 바뀌지 않는다. 인덱스나 페이지 방식 변경은 더 큰 규모와 실제 데이터 분포를 본 뒤 판단한다.
