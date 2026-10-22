# 공개 준비: Python 전이 의존성 패치

## 확인한 위험과 영향 경로

2026-10-22 GitHub Dependabot open alert 10개를 조회했다. 이번 단위는 uv.lock의 두 Python
패키지에 한정하며 나머지 npm alert를 해결하거나 무시 처리하지 않는다.

| 패키지 | 잠금 변경 | advisory와 이 프로젝트의 경로 |
| --- | --- | --- |
| certifi | 2026.7.22 → 2026.10.19 | GHSA-6q48-6c7w-9gw2, critical. 폐기된 중간 CA 키와 연결된 root를 포함한 번들. httpx/OpenAI의 HTTPS trust 경로이며 서버의 AI 비활성만으로 패치가 불필요해지는 것은 아니다 |
| Mako | 1.4.1 → 1.4.3 | GHSA-5639-2j2p-m4mx, medium, 수정 최소 1.4.2. Alembic 전이 의존성. 앱에 사용자 URI를 받는 TemplateLookup 호출은 발견하지 않았지만 Windows 개발 환경까지 같은 patch 계열로 갱신 |

## 선택

`uv lock --upgrade-package certifi --upgrade-package mako`로 두 항목의 version/hash만 바꿨다.
새 라이브러리·직접 의존성·framework major 변경은 없다. PyPI 원본 wheel/sdist와 SHA256을 잠근다.
기존 환경의 작업 도구를 보존하는 로컬 `uv sync --frozen --inexact --project apps/api`로 설치했다.
CI와 Docker는 기존 frozen 설치를 유지한다. 인증서 검증을 끄거나 CA 실패 시 우회하지 않는다.
Supabase의 별도 pinned CA/verify-full 설정은 변경하지 않는다.

설치 버전 certifi=2026.10.19, Mako=1.4.3을 확인했고 새 certifi bundle로 SSLContext를 생성했을 때
hostname verification과 CERT_REQUIRED가 유지됐다. 이것은 실제 외부 HTTPS/공격 재현 증거는 아니다.
API/AI provider 코드 변경과 유료 provider 호출은 없다. 기존 API 회귀·migration/container smoke를 검증한다.

설치 후 전체 API **220 passed / 18.47초**(cp949 기본 모드), Ruff app/tests/alembic,
strict mypy app/tests 110 source files 통과. PR의 frozen install/build/E2E/container-smoke는 별도 CI로 확인한다.

## 배포 및 남은 범위

lock 변경의 병합과 실행 중인 image 교체를 구분한다. 변경 준비 당시 private service SHA `2dfb0d0`는
이전 bundle을 포함했다. 이후 PR #24/25와 main CI를 통과한 `1b11879` image로
[release 39708645497](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39708645497)가 성공했고 deploy-SA HTTP 4/4를 검증했다.
GitHub 재조회에서 Python open alert 0개를 확인했으며 수동 dismissed 처리하지 않았다.
남은 npm alert는 실제 runtime/build 경로와 upstream patch를 별도 검토한다. 현재 공개 전환은 하지 않는다.

근거:
- [certifi 공식 advisory](https://github.com/advisories/GHSA-6q48-6c7w-9gw2)
- [Mako 공식 advisory](https://github.com/advisories/GHSA-5639-2j2p-m4mx)
