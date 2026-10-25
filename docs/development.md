# 개발 환경

[프로젝트 소개](../README.md) · [API 가이드](api/README.md)

## 환경 변수 관리

`.env.example`은 필요한 변수 이름과 로컬 예시값을 공유하는 템플릿으로 Git에 포함합니다.
실제 API 키·운영 DB 비밀번호·세션 서명 키는 넣지 않습니다.
로컬 설정은 `.env` 또는 `apps/api/.env`에 저장하고, 배포 비밀값은 Secret Manager로 전달합니다.
`.env`와 `.env.*`는 Git에서 제외하며 `.env.example`·`.env.local.example` 같은 예시 템플릿만 예외입니다.
예시의 `jhworks-local` 비밀번호는 로컬 Compose DB 전용이고, JWT 값은 교체용 문구입니다.

```bash
cp .env.example .env
```

[참고: 예시 파일과 비밀 설정 분리](https://github.com/laravel/docs/blob/13.x/configuration.md#environment-configuration)

## 로컬 테스트 계정

공통 비밀번호: `demo1234`

이 계정은 로컬 개발·테스트 전용이다. 기본 seed는 development/test의 SQLite 또는
localhost/loopback/로컬 Compose `db` PostgreSQL에서만 실행되며 원격 DB와 staging/production은
연결 전에 거부한다. 공개 서비스에는 이 비밀번호를 등록하지 않는다.
[실행 경계와 검증](engineering/local-seed-boundary.md)을 참고한다.

| 역할 | 이메일 | 가능한 작업 |
| --- | --- | --- |
| 작성자 윤서진 | `seojin.yoon@jhworks.test` | Draft 작성·제출·재작성 |
| 결재자 최도윤 | `doyun.choi@jhworks.test` | Sales 문서 승인·반려 |
| 정책 운영 한가람 | `garam.han@jhworks.test` | 가상 정책 조회 |

이 계정은 local portfolio demo 전용이며 실제 인증 시스템을 나타내지 않는다.

## Docker 실행

Requirements: Docker Engine과 Docker Compose v2 plugin

```bash
cp .env.example .env
docker compose up --build
```

Compose는 migration과 synthetic seed를 완료한 뒤 API와 web을 기동한다. 배포 계약을 확인하려면 별도 terminal에서
읽기 전용 smoke를 실행한다.

```bash
pnpm smoke:deployment
```

정책 RAG를 처음 사용할 때는 다른 terminal에서 active policy section을 한 번 색인한다.

```bash
docker compose exec api python -m app.scripts.index_policies
```

- Web: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- API health: `http://localhost:8000/api/v1/health`

별도 release 단계가 migration과 idempotent seed를 완료한 뒤 API container가 시작한다.

API key가 없어도 일반 결재 기능은 모두 사용할 수 있다. AI 기능은 각 기능별 안전한 `503`으로 실패하며 업무 데이터는 변경되지 않는다.

## 로컬 개발

Requirements: Node.js 24+, pnpm 10+, Python 3.12+, uv

```bash
pnpm install
uv sync --project apps/api
pnpm db:migrate
pnpm db:seed
```

AI가 필요 없는 개발에는 키가 필요하지 않다. 실제 모델 호출은 비용이 발생한다. 키는 채팅이나 Git에 넣지 않고 `python3 tools/store_openai_key.py`의 숨김 입력으로 저장할 수 있다. AI를 활성화할 때만 아래 모델·기능 설정을 별도로 확인한다.

```dotenv
JHWORKS_OPENAI_MODEL=gpt-5.4-mini
JHWORKS_POLICY_EMBEDDING_MODEL=text-embedding-3-small
JHWORKS_APPROVAL_DRAFT_CONFIRMATION_TTL_MINUTES=15
JHWORKS_LEAVE_DRAFT_CONFIRMATION_TTL_MINUTES=15
JHWORKS_LEAVE_SUBMIT_CONFIRMATION_TTL_MINUTES=10
```

`.env`는 Git에 포함하지 않는다. API key는 browser에 전달되지 않고 FastAPI에서만 사용한다.

최초 1회 또는 정책 내용·embedding model 변경 후 정책 인덱스를 갱신한다. 변경되지 않은 section은 다시 호출하지 않는다.

```bash
pnpm policy:index
```

두 terminal에서 실행한다.

```bash
pnpm dev:api
pnpm dev:web
```

기본 local database는 SQLite다. PostgreSQL과 동일한 환경은 Docker Compose를 사용한다.

## 검증

```bash
pnpm validate
pnpm exec playwright install chromium
pnpm test:e2e
pnpm test:e2e:public-demo
```

일반 검증과 브라우저 테스트는 외부 AI를 호출하지 않는다. PostgreSQL 통합 테스트는 CI의 별도 서비스에서 실행한다. 실제 모델 평가는 `pnpm eval:all` 등 별도 명령이며 유료 호출이 발생하므로 일반 CI에 포함하지 않는다.

## JHW Pattern 개발

토큰·Button·Badge는 `packages/pattern`에서 관리하고 앱과 `/pattern` 문서가 함께 소비합니다.

```bash
pnpm --filter @jhworks/pattern build
pnpm check:pattern
pnpm --filter @jhworks/pattern pack --pack-destination ./artifacts/pattern
```

토큰 생성물 일치, 주요 텍스트 색상 쌍의 4.5:1 대비와 패키지 계약은 `pnpm validate`에 포함됩니다.
전체 UI의 접근성 인증을 의미하지는 않습니다. npm 게시 전에는 이름·소유권·라이선스·안정 API를 확정합니다.
[원칙·출처·검증 범위](design/ux-principles.md)를 참고합니다.

## Tailwind와 컴포넌트 문서

앱은 Tailwind 4의 `tw:` 유틸리티와 JHW 토큰 bridge를 사용합니다. Preflight는 제외하며,
사이드바부터 전환하고 기존 CSS는 영역별로 이전합니다. 공통 패키지는 CSS 진입점도 계속 제공합니다.
[스타일 도구의 역할·적용 범위·Storybook 도입 기준](design/styling.md)을 참고하세요.

## 경비 평가의 offline/실제 모델 구분

`pnpm eval:expense:offline`은 36개 사례의 데이터 계약만 검사하며 설정·DB·모델 SDK를 불러오지 않습니다.
보고서의 모델 정확도·지연·토큰은 null이고 providerCalls는 0입니다. 이 검사는 validate에도 포함됩니다.
기존 `eval:approval-draft`와 `eval:all`은 외부 모델 평가 경로이며 비용이 발생할 수 있으므로 구분해서 사용하세요.
[대표 경비 계약](product/expense-settlement-contract.md), [평가 범위와 재현](engineering/expense-evaluation-contracts.md)을 참고하세요.
