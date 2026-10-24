# JHWorks AI Groupware

**자연어 업무 요청을 검토 가능한 결재 문서로 연결하는 풀스택 그룹웨어.**

“이번 CES 출장에서 쓴 17만원, 경비 정산 올려줘.”

업무 요청에는 금액만 있고 사용처·지출일·증빙·정책 근거가 빠지기 쉽습니다. JHWorks는 요청을 양식으로 구조화하고, 누락 정보를 묻고, 관련 규정을 제시한 뒤 사용자가 확인한 내용만 저장·제출하도록 설계했습니다. 결재자는 같은 문서와 이력을 확인하고 승인하거나 반려합니다.

[라이브 데모](https://groupware.pikan.dev) · [Swagger](https://groupware.pikan.dev/api/v1/docs) · [아키텍처](docs/architecture/README.md) · [포트폴리오](https://pikan.dev/ko/projects/jhworks-ai-groupware)

> **공개 체험에서는 유료 AI 호출을 꺼 두었습니다.** 직접 작성 → 제출 → 결재자 역할 전환 → 승인을 체험할 수 있습니다. 자연어 초안·정책 RAG·AI 검토는 별도로 구현·검증한 기능이며 아래에서 범위를 구분합니다.

## 대표 업무: 출장 경비 정산

1. 로그인 없이 체험을 시작합니다. 방문자마다 합성 조직과 업무 공간을 분리합니다.
2. **직접 작성 → 경비 정산**에서 지출일·사용처·금액·비용 구분·업무 목적을 입력합니다.
3. 임시저장한 문서에서 누락 정보와 중복 후보를 확인합니다. 증빙 참조는 문서번호이며 원본 파일은 업로드하지 않습니다.
4. 문서·금액·버전을 확인하고 제출합니다. 서버가 작성자의 관리자를 결재자로 지정합니다.
5. **결재자로 체험하기**로 전환해 승인·반려합니다. 작성자 역할에서 처리 결과와 결재 이력을 확인할 수 있습니다.

![공개 체험 업무 홈](docs/portfolio/screenshots/public-home-desktop.png)

![경비 정산 승인 화면](docs/portfolio/screenshots/public-expense-approved-desktop.png)

위 화면은 외부 AI를 호출하지 않는 공개 모드 회귀 테스트에서 촬영했습니다. 실제 UI와 API를 사용하며 데이터는 합성입니다.

## 구현에서 보여 주려는 역량

| 영역 | 구현과 설계 선택 | 확인할 곳 |
| --- | --- | --- |
| 풀스택·데이터 | FastAPI 모듈 구조, 명령별 권한·상태 전이, version 비교, 결재·연차의 원자적 갱신, Alembic | [아키텍처와 데이터 관계](docs/architecture/README.md), [API 가이드](docs/api/README.md) |
| 프론트엔드 | Next.js App Router·TypeScript, 공통 화면 셸·업무 컴포넌트, 색상·간격·타이포·모션 토큰 | [UI 토큰](apps/web/src/app/globals.css), [업무 컴포넌트](apps/web/src/components) |
| UI/UX | 업무 홈에서 다음 행동 안내, 양식별 입력, 역할 전환, 문서·금액 확인 창, 반응형 화면·키보드 조작 | [브라우저 검증](e2e), [공개 데모](https://groupware.pikan.dev) |
| 기업 업무 AI | 자연어 구조화·후속 질문, 정책 RAG와 인용 검증, 사용자 범위 Tool, 저장·제출을 분리한 확인 | [AI와 통제 설계](docs/portfolio/architecture-and-controls.md), [휴가 workflow ADR](docs/adr/0001-durable-leave-agent-state-machine.md) |
| 인프라·운영 | Cloud Run·PostgreSQL, 동일 출처 API 프록시, CI·수동 release·smoke, 방문자 격리·쓰기 예산 | [배포 구조](docs/architecture/README.md), [release runbook](docs/operations/release-runbook.md) |

현재 version 검증은 **서버의 낙관적 동시성 제어**입니다. 성공 전에 화면을 갱신하는 낙관적 UI와는 구분합니다.

## AI가 맡는 일과 서버가 책임지는 일

| 기능 | AI의 역할 | 서버의 책임 |
| --- | --- | --- |
| 결재 초안 | 요청 유형·날짜·금액을 구조화하고 모호한 정보를 질문 | 양식·필수 항목 검증, 저장 전 미리보기, 확인 토큰·멱등 저장 |
| 문서 검토·정책 RAG | 의미상 누락과 관련 정책 설명 | 숫자·날짜·권한 검사, 검색된 정책만 인용 허용, 오래된 검토 결과 차단 |
| 업무 조회 Tool | 현재 사용자 업무를 조회할 Tool 선택 | actor 범위 제한, 인자 검증, 호출 횟수 제한·실행 기록 |
| 휴가 상담·신청 | 희망 기간 해석, 계산된 후보와 근거 설명 | 잔여 연차·일정·휴일 계산, 저장과 제출의 별도 확인, 변경 직전 재검증 |

AI가 자율 승인하거나 임의의 DB 쿼리를 실행하지 않습니다. 휴가 workflow는 상담 → 초안 확인 → 제출 확인을 DB 상태 머신으로 보존합니다.
실제 모델은 고정 합성 경비 사례 **2건**을 확인했습니다. 이는 전체 정확도나 실사용 성과를 증명하는 결과가 아닙니다. [모델 검증 범위](docs/engineering/expense-model-smoke.md).

## 아키텍처

```mermaid
flowchart LR
    Browser["방문자"] --> Hosting["Firebase Hosting"]
    Hosting --> Web["Cloud Run / Next.js"]
    Web -->|"동일 출처 /api/v1"| API["FastAPI sidecar"]
    API --> DB["Supabase PostgreSQL + pgvector"]
    API -.->|"구현됨 / 공개 OFF"| AI["OpenAI adapters"]
```

백엔드는 도메인·서비스·외부 AI 어댑터를 나눈 모듈형 모놀리스입니다. 세션과 권한은 서버에서 검증하고, 상태를 임의 PATCH하는 대신 `submit / approve / reject / revise` 명령으로 전이합니다.

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> PENDING: 작성자 제출
    PENDING --> APPROVED: 결재자 승인
    PENDING --> REJECTED: 결재자 반려
    REJECTED --> DRAFT: 재작성 · 이전 회차 보존
```

[전체 아키텍처 문서](docs/architecture/README.md)에는 배포 구성, 내부 책임, 경비 시퀀스, 데이터 관계, 배포 흐름의 다섯 그림을 정리했습니다. [Swagger](https://groupware.pikan.dev/api/v1/docs)에서는 API별 요청·응답과 인증 구조를 확인할 수 있습니다. 공개 문서의 요청 실행은 비활성화했습니다.

## 실행과 검증

Node.js 24+, pnpm 10+, Python 3.12+, uv를 사용합니다. API 키 없이 일반 업무 흐름을 실행할 수 있습니다.

```bash
pnpm install
uv sync --project apps/api
pnpm db:migrate
pnpm db:seed
```

각 터미널에서 `pnpm dev:api`, `pnpm dev:web`을 실행합니다. Web은 `http://localhost:3000`, API 문서는 `http://localhost:8000/docs`입니다.

[로컬 계정·Docker·AI 설정](docs/development.md) · [기여 가이드](CONTRIBUTING.md) · [코드 컨벤션](docs/code-conventions.md)

```bash
pnpm validate                 # lint · 타입 · API 테스트 · Web production build
pnpm test:e2e                 # 일반 업무 · 합성 AI · desktop/mobile
pnpm test:e2e:public-demo     # AI OFF · 공개 방문자 작성/제출/승인
```

일반 CI는 외부 AI를 호출하지 않습니다. PostgreSQL 통합 테스트와 컨테이너 smoke를 별도로 실행하며, 실제 모델 평가는 비용이 발생하는 명령으로 분리했습니다. 최신 배포·검증 근거는 [현재 상태](docs/engineering/current-status.md)와 각 PR에서 확인할 수 있습니다.

## 공개 범위와 다음 단계

- 일반·출장·경비·휴가 작성, 제출, 역할 전환, 승인·반려를 공개합니다. 조직·정책·계정·업무 데이터는 모두 가상이며 과거 회사의 제품·자산을 재현하지 않았습니다.
- 체험은 **15분 / 하루 시작 20회 / 보관 30공간**으로 제한합니다. 자동 정리는 꺼져 있어 보관 상한에 닿으면 새 체험이 중단될 수 있습니다.
- Cloud Run 월 5천원 spend cap과 프로젝트 전체 월 1만원 알림을 설정했습니다. 집계 지연·다른 서비스 비용 때문에 총 청구액의 절대 상한은 아닙니다.
- 공개 AI 활성화, 자동 정리 운영, 예약 백업, main 자동 배포는 후속 과제입니다. 실제 기업의 업무 시간 절감은 아직 측정하지 않았습니다.
- ERP 재고 선제안·인재 관리까지 구현한 범용 ERP는 아닙니다. 현재 대표 과업인 **요청 → 정산 문서 → 검토 → 결재**의 완결성과 증거를 우선합니다.

[세부 로드맵](docs/engineering/roadmap.md) · [설계 결정](docs/adr) · [제품 명세](docs/product)
