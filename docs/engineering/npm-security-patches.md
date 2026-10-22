# npm 전이 의존성 보안 패치 — 2026-10-22

## 문제와 검증 기준

동일 pnpm 10.30.3 / 동일 날짜 npm audit에서 main lockfile은 8 findings(High 6 / Moderate 2)였다.
개수는 advisory × 설치 버전 경로의 결과이며 고유 CVE 수가 아니다.
범위는 수정 버전이 있는 3개의 package version을 갱신하고 기존 앱 lint/type/build/browser/container 계약을 유지하는 것이다.

| 전이 패키지 | 이전 | 선택한 수정 버전 | 소비 경로 |
| --- | --- | --- | --- |
| brace-expansion 1.x | 1.1.18 | 1.1.21 | minimatch 3 → ESLint/plugin/config |
| brace-expansion 5.x | 5.0.9 | 5.0.12 | minimatch 10 → typescript-estree → eslint-config-next |
| js-yaml 4.x | 4.3.1 | 4.3.2 | eslintrc → ESLint |

공식 [brace-expansion advisory](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr)와
[js-yaml advisory](https://github.com/advisories/GHSA-2883-xcg3-v3hh)의 fixed range를 확인했다.
기존 세부 recursion advisory도 해당 버전으로 함께 벗어난다.

## 선택과 원리

전체 Next.js/ESLint major 갱신은 현재 필요보다 범위가 크다. application 코드나 라이브러리를 새로 추가하지 않고
기존 workspace overrides에 major별 고정 버전을 적용했다. pnpm은 소비자가 요청한 전이 의존성의 해석 결과를 바꾸고
lockfile에는 실제 package/integrity/소비 경로를 기록한다.

1.x CommonJS 소비자를 5.x ESM으로 강제 통일하지 않는다. selector는 brace-expansion@1 / @5, js-yaml@4로 제한한다.
lockfile diff는 이 세 package 버전·integrity·snapshot 및 override 설정뿐이다. 직접 의존성은 변경하지 않는다.
상위 패키지가 안전한 범위를 채택하면 overrides를 제거하고 frozen install·동일 검사를 반복한다.

## 실제 검증

- baseline: main의 package/workspace/lock/web manifest만 별도 임시 폴더에 복사해 pnpm audit --json 실행.
  High 6 / Moderate 2, 총 8 findings, exit 1.
- after: 변경 lockfile의 동일 명령에서 High 1 / Moderate 0, 총 1 finding, exit 1.
  남은 항목은 braces GHSA-vfj7-8cjw-p6xm이다. audit 실패를 숨기거나 통과로 바꾸지 않는다.
- pnpm install --frozen-lockfile --ignore-scripts 성공. 이미 설치된 개발환경에서 검증용 설치였으며 CI/Docker의 기존 install 정책은 바꾸지 않았다.
- pnpm lint:web / type-check:web / build:web 성공. Next production compile 5.5초는 이번 단일 실행의 로그이며 개선 수치가 아니다.
- git diff --check로 변경 형식을 확인한다. PR CI의 E2E/container 결과는 별도 checks에서 확인한다.
- 원본 audit JSON은 ignored artifacts/cloud-run에 보관한다. registry 결과는 시간에 따라 달라지므로 버전/날짜/잔여 advisory를 함께 기록한다.

## 남은 위험과 다음 검증

[braces 3.0.3의 stack exhaustion](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)은 현재 patched version이 없다.
pnpm why에서 fast-glob → micromatch → braces가 eslint-config-next 개발 의존성 경로인 것을 확인했다.
GitHub/npm audit은 scope를 runtime/dependencies로 표시하므로 이 분류만으로 실제 요청 경로 노출을 판단하지 않는다.
production bundle/최종 Linux 이미지의 포함 여부와 앱의 비신뢰 pattern 유입 여부는 별도 검증이 필요하다.
경고는 dismiss하지 않고 upstream fixed release와 최종 이미지 의존 경로를 추적한다.
새 Major나 임의 fork를 근거 없이 도입하거나 알려진 경고를 CI에서 전역 무시하지 않는다.

이 패치는 공개 demo의 요청 제한·tenant 격리·AI 비용 제한을 대신하지 않는다. private staging/AI off 정책은 유지한다.
면접에서는 “개발 의존성 경고를 왜 무시하지 않았는가?”, “왜 모든 소비자에 최신 major를 강제하지 않는가?”,
“audit findings 수와 실제 공격 가능한 경로를 어떻게 구분하는가?”를 이 diff와 실제 검사 결과로 설명할 수 있다.
