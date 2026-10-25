# 공통 조회와 세션 수명 — M3-01

홈·AI 초안·직접 작성에서 반복하던 설정/계정 조회를 세션 단위로 공유한다.
로그인·체험 시작·역할 변경·로그아웃·현재 세션401 때 캐시와 페이지 상태를 함께 비운다.

## 선택과 범위

Context만으로 공유하면 의존성을 추가하지 않아도 되지만, 중복 요청 합류·취소·신선도·
오류·재검증 상태를 직접 관리해야 한다. 현재 두 훅이 서로 다른 페이지와 중첩 컴포넌트에서
쓰이므로 TanStack Query `5.104.5`를 선택했다. 기존 훅의 반환 형태를 유지한다.

[QueryClientProvider](https://tanstack.com/query/latest/docs/framework/react/reference/functions/QueryClientProvider)로
root 인스턴스별 client를 만들고, [useQuery](https://tanstack.com/query/latest/docs/framework/react/reference/functions/useQuery)의
AbortSignal·동일 키 공유·staleTime을 사용한다.
[QueryClient](https://tanstack.com/query/latest/docs/framework/react/reference/classes/QueryClient)의
취소·무효화·clear로 세션 경계를 처리한다. 서버 전역 singleton이나 브라우저 영구 저장은 없다.

| 데이터 | 키 | 수명 / 갱신 |
| --- | --- | --- |
| 체험·AI 설정 | `session / generation / configuration` | 30초 fresh, 오류 시 과거 capability 사용 금지 |
| 현재 계정 | `session / generation / employee` | 30초 fresh, 오류 시 과거 계정 사용 금지 |
| 미사용 공통 조회 | 동일 | 마지막 observer 해제 후 5분 GC |
| 업무 목록·상세·mutation | 기존 경로 | 이번 변경에서 query cache로 옮기지 않음 |

자동 재시도는0이다. 활성 공통 조회는 focus/visible/online 때 무효화 후 재검증한다.
동시에 도착한 focus와 visibility는 진행 중 요청을 취소하지 않고 합류한다.
서버 권한·workspace 만료 검사는 모든 API에서 계속 수행하며 UI 캐시가 권한을 부여하지 않는다.

## 경계 처리

- 성공한 인증 변경은 generation을 올리고 진행 중 공통 조회 취소·캐시 clear·하위 페이지 remount를 수행한다.
  페이지 부모가 가진 입력/상담/상세 상태도 이전 계정에서 넘어오지 않는다.
- 다른 탭에서 쿠키를 바꾼 경우 focus 조회의 직원ID·역할·부서·관리자 fingerprint 변경으로 같은 초기화를 수행한다.
- 정상적인 동일 계정 재검증 동안 업무 본문은 숨기되 remount하지 않아 입력을 보존한다.
- API 요청은 시작 시 generation을 기억한다. 현재 generation의401만 로그인으로 보낸다.
  이미 취소됐거나 이전 계정의 늦은401은 새 계정을 로그아웃시키지 않는다.
- 공개 `/feedback`은 자체 만료 복구가 있어401 때 캐시는 비우되 로그인으로 보내거나 폼을 remount하지 않는다.
  재연결 성공은 인증 변경 이벤트로 새 세션 조회를 사용하며, 의견·동의 값은 메모리에 유지한다.
- 잘못된 비밀번호의 `/auth/login`401은 세션 만료로 처리하지 않아 입력/오류 안내를 유지한다.
- 로그아웃은 기존 계정별 AI 요청 전달값도 지운다. 공통 조회를 localStorage 등에 저장하지 않는다.
- 업무 mutation은 기존 저장 후 상세/목록 이동·재조회 계약을 유지한다. 로그인/체험 시작/역할/로그아웃 mutation만
  이번 공통 캐시 무효화 대상으로 연결했다. 업무 데이터 캐시 도입 시 별도의 mutation별 무효화가 필요하다.

## 측정과 검증

비교 기준은 원래 FE 소스 `af4ac87d45181cf23e5ed96dd369afac57054605`에서 측정했다.
실제 API/domain과 임시 DB·합성 provider를 사용하는 Playwright dev 환경이다.
각 fresh browser에서 `/login`→로그인→홈→AI 초안 링크→새 결재 작성 링크로 이동하고
각 단계 networkidle 뒤 해당 GET의 **200 응답 수**를 누적했다. PC(Desktop Chrome)와
모바일(iPhone13, Chromium) 결과가 같았다.

| 누적 지점 | 기존 설정 / 계정 | 변경 후 설정 / 계정 |
| --- | --- | --- |
| 홈 | 3 / 1 | 2 / 1 |
| AI 초안 | 6 / 2 | 2 / 1 |
| 직접 작성 | 7 / 3 | 2 / 1 |

설정2회는 로그인 전/후 세션 경계에서 각각 한 번이다. 개발 StrictMode의 취소된 요청이나
서버가 이미 수신한 요청은 이 집계에서 제외되므로 전체 HTTP 시도 수 감소율로 해석하지 않는다.
사람의 과제 시간·실제 배포 지연 개선을 측정한 결과도 아니다.
기존 기록은 `/tmp/jhw-session-baseline.log`, 변경 후 재현은 `e2e/session-data.spec.ts`와
Git 제외 `artifacts/session-data/after-{desktop,mobile}.json`이다.

PC/모바일 회귀는 공통 조회 합류, 정상 focus 입력 보존, 이전 계정의 늦은200/401,
외부 쿠키 변경에 따른 입력 초기화, 현재401 후 재로그인, 로그인 실패 입력 보존을 검증한다.
취소 신호가 없는 이전 AI 요청의 늦은401도 새 계정을 로그아웃시키지 않는지 별도로 확인한다.
기존 역할 전환·AI capability·상담·결재 및 production CSP 회귀도 CI에서 실행한다.
이 변경은 아직 공개 서비스에 배포하지 않았다.

로컬 검증: `pnpm validate` 통과(API584건, PostgreSQL 전용33건 로컬 제외), 관련 E2E40건,
추가 회귀 포함 세션 E2E16건, 공개 체험10건, production CSP·경비 흐름4건 통과.
각 테스트 묶음은 중복되므로 합산해 고유 테스트 수로 표시하지 않는다. PostgreSQL은 PR CI에서 실행한다.

첫 PR CI의 피드백 복구2건 실패로 전역401 리디렉션이 기존 공개 폼 계약을 깨뜨린 것을 확인했다.
공개 피드백에만 안정적인 subtree key와 자체 복구를 허용하고, 인증 캐시 초기화는 유지하도록 수정했다.
