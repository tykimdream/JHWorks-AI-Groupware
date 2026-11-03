# 결재 목록 HTTP·브라우저 합성 측정 — 2026-11-03

main `8b28d65`에 이 측정 도구를 추가한 작업 트리에서 측정했다. 전용 테스트 서버는 임시 SQLite DB에 합성 경비 1,000건(각 결재선 2개)을 만들고 종료 시 폐기한다. 로그인도 기존 합성 Demo 계정을 사용하며 외부 데이터·모델 호출은 없다. 배포 앱에 테스트 서버를 포함하지 않는다.

```sh
NEXT_PUBLIC_API_URL=/api/v1 API_PROXY_TARGET=http://127.0.0.1:8100 pnpm build:web
pnpm exec playwright test --config=playwright.performance.config.ts
```

Production standalone 웹과 로컬 API를 같은 출처 프록시로 연결한다. 인증된 브라우저 fetch에서 기존 전체 목록과 요약 첫 페이지를 순서대로 1회 warm-up 후 각 5회 호출한다. 응답을 끝까지 읽은 시간과 **브라우저가 압축 해제한 body bytes**를 기록한다. 로그인 시간은 포함하지 않지만 인증 처리와 프록시, 로컬 전송은 포함한다. 현재 요약 화면은 navigation 시작부터 Playwright가 20개 행을 확인할 때까지 1회 warm-up 후 5회 기록한다. 이 시간에는 자동화 polling 지연이 포함되고 실제 페인트 완료를 정확히 측정하지 않는다. 기존 전체 목록 화면은 재현하지 않았으므로 화면 전후 비교가 아니다.

| Chromium 환경 | 기존 전체: 행 / bytes / HTTP 중앙값 | 요약 첫 페이지: 행 / bytes / HTTP 중앙값 | 현재 화면 20행 확인 중앙값 |
| --- | --- | --- | --- |
| PC | 1,000 / 2,145,024 / 97.3ms | 20 / 11,306 / 4.9ms | 130.0ms |
| 모바일 에뮬레이션 | 1,000 / 2,145,024 / 100.9ms | 20 / 11,306 / 4.8ms | 130.6ms |

[PC 원시 샘플](benchmarks/approval-http-browser-desktop-2026-11-03.json), [모바일 원시 샘플](benchmarks/approval-http-browser-mobile-2026-11-03.json). 브라우저는 둘 다 Chromium이며 모바일은 실제 기기가 아니다. 서로 다른 행 수와 응답 계약을 비교한 결과이고, SQLite·단일 사용자·로컬 환경의 따뜻한 캐시에서 한 번 실행했다. 압축 전송량, PostgreSQL을 포함한 end-to-end 지연, 동시 부하, 공개 workspace, 큰 offset, 실제 네트워크와 사용자 체감 성능을 나타내지 않는다. CI는 시간 임계값으로 합격 여부를 정하지 않고 원시 샘플을 artifact에 보관한다.
