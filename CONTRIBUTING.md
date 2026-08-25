# JHWorks AI Groupware 기여 가이드

이 문서는 변경을 작고 검증 가능하게 만들기 위한 진입점이다. 구체적인 구현 규칙은 [코드 컨벤션](docs/code-conventions.md)을 따른다.

## 프로젝트 독립성

- 과거 회사의 소스코드, UI, 컴포넌트, 데이터베이스 schema, API 명세, 내부 문서, 규정, 실제 인물·조직·업무 데이터, 비공개 업무 흐름을 사용하거나 재현하지 않는다.
- 일반적인 Enterprise software 경험과 공개 표준만 활용하며 JHWorks AI Groupware의 제품 구조와 구현은 처음부터 독립적으로 설계한다.
- 예제와 테스트에는 JHWorks를 위해 만든 synthetic data만 사용한다.
- 출처나 사용 권한이 불명확한 자산은 PR에 포함하지 않는다.

## 작업 흐름

1. 해결할 문제와 완료 조건을 이슈 또는 작업 문서에 먼저 적는다.
2. `type/short-description` 형식으로 브랜치를 만든다.
3. 구현과 함께 테스트·평가 데이터·관련 문서를 갱신한다.
4. 로컬 자동 검증을 실행한다.
5. PR 템플릿에 재현 가능한 검증 결과와 위험을 기록한다.
6. 최소 한 명의 리뷰와 필수 CI 통과 후 병합한다.

초기 프로젝트 단계에서 스크립트와 CI가 확정되기 전에는 실행한 명령을 PR에 직접 기록한다. 명령이 확정되면 이 문서와 CI를 함께 갱신해 문서와 실제 검증이 어긋나지 않게 한다.

## Git 규칙

### 브랜치

형식은 `type/short-description`이다. 개인 이름은 협업과 자동화에 의미가 없으므로 넣지 않는다.

사용 가능한 type은 `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `ci`, `perf`, `revert`이다.

예시:

- `feat/approval-review`
- `fix/policy-citation-order`
- `docs/agent-safety`

### 커밋

[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) 형식을 사용한다.

```text
<type>: <summary>
```

예시:

```text
feat: add structured approval findings
fix: reject unauthorized employee lookup
docs: define AI review checklist
```

- 제목은 하나의 변경을 명령형으로 설명하고 마침표를 붙이지 않는다.
- scope 괄호는 사용하지 않는다. 변경 영역은 브랜치명, PR 제목과 본문에서 설명한다.
- 하위 호환성을 깨는 변경은 `!`와 본문의 `BREAKING CHANGE:`로 명시한다.
- 이슈를 자동 종료하려면 본문 또는 PR에 `Closes #123`을 쓴다.
- 포맷 변경과 기능 변경은 가능하면 별도 커밋으로 나눈다.

## PR 원칙

- 하나의 PR은 하나의 목적을 가진다. 변경 이유를 설명하기 어려우면 먼저 나눈다.
- 생성 코드, lockfile, 대규모 포맷 변경은 비즈니스 로직 변경과 분리한다.
- 작성자가 PR 템플릿의 모든 항목을 검토하되, 해당 없는 조건부 섹션은 삭제할 수 있다.
- 리뷰어는 코드 스타일보다 정확성, 권한, 데이터 변경 안전성, 실패 처리, 테스트 증거를 우선한다. 스타일은 가능한 한 도구로 검사한다.
- 긴 논의가 필요한 구조 변경은 구현 전에 ADR로 남긴다.

## 문서 관리

- 동작 또는 계약을 바꾸는 PR은 같은 PR에서 문서도 갱신한다.
- 새 규칙은 이유, 적용 범위, 자동 검증 방법을 함께 제안한다.
- 규칙은 실제 설정과 충돌할 수 없다. 충돌하면 formatter, linter, type checker, test/CI 설정이 실행 가능한 기준이며 문서를 즉시 수정한다.
- 채택된 중요한 설계 결정은 `docs/adr/`에 ADR로 기록한다. 최초 ADR이 생길 때 인덱스와 템플릿을 추가한다.
- 더 이상 유효하지 않은 규칙은 남겨 두지 않고 Git 이력으로 추적한다.
