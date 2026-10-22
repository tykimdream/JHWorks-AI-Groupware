# 공개 데모 모드의 별도 비공개 리허설 서비스

## 목적과 선택

기존 jhworks-staging은 private IAM/일반 로그인 업무 검증을 위한 서비스다. 이를 바로 공개 데모 모드로
바꾸면 기존 검증 경로와 public IAM을 거부하는 release runner 계약이 뒤섞인다. 기존 경로를 유지하고
동일한 검증 image를 사용하는 `jhworks-demo` Service manifest를 별도 파일로 생성한다.
이는 실제 서비스 생성/공개 승인이 아니며, 우선 IAM 비공개 상태에서 guest 흐름을 검증하기 위한 준비다.

서비스를 나누면 cold start/기동 검증과 새 자원의 사용량 과금이 생기지만, 기존 private 서비스의
traffic/환경변수를 바꾸지 않고 실패한 후보를 점검할 수 있다. 같은 서비스를 수시로 모드 전환하거나
기존 private release의 IAM 검사를 완화하는 대안은 제외했다. 새 배포 플랫폼/의존성은 없다.

## 구현 계약

- 기존 ReleaseSettings/service_manifest의 image/설정 검증과 web+API sidecar 구성을 재사용한다.
  기존 private runner/WIF/workflow 코드는 수정하지 않는다.
- service는 jhworks-demo, origin은 https://groupware.pikan.dev로 고정한다. private staging 이름이나
  유사 도메인/다른 origin, max>1, concurrency>4는 거부한다. SHA40자리·같은 project/region의 digest만 받는다.
- 서비스 전체 max=1/min=0, CPU 각1·메모리 각512MiB, concurrency4, timeout55초로 제한한다.
- API 공개 데모 모드 true, AI false, 체험15분/일20회/보관공간30개, Secure/HttpOnly/Lax를 유지한다.
  서버의 workspace별100요청/20쓰기 예산은 기존 구현을 사용한다.
- Firebase Hosting이 전달하는 `__session` 쿠키 이름을 사용한다. 호스트는 명시적인 custom origin으로 묶는다.
- invoker IAM check를 끄지 않는다. 이 generator는 IAM grant·DNS·Hosting rewrite·migration Job을 생성하지 않는다.
  **Manifest만으로 기존 IAM policy가 비공개라고 보증하지는 않는다.** 생성 전 이름 충돌/정책을 조회하고,
  생성 후 project/service public binding 없음과 익명403을 확인해야 한다.

기존 release 설정 형식을 재사용하므로 예시 파일에 migration 설정 필드가 있지만, 생성하는 Service에는
runtime DB/session 참조만 들어가며 migration 계정/Secret은 들어가지 않는다. 설정의 계정 이름이 실제
최소 권한을 증명하지 않으므로 적용 시 IAM/DB grants와 승인한 실제 참조를 대조한다.
예시의 기존 runtime/session 참조는 **비공개 리허설용**이다. 인터넷 공개 전에 전용 실행 계정·DB 접근·
서명키 분리 필요성과 실제 private 합성 자료 접근 경계를 검토한다. 이 파일을 그대로 공개 승인으로 해석하지 않는다.

```sh
cd apps/api
uv run python -m app.ops.public_demo_manifest \
  --settings ../../deploy/cloud-run/public-demo.example.json \
  --api-image 'asia-northeast3-docker.pkg.dev/replace-project/jhworks/api@sha256:<64자리 digest>' \
  --web-image 'asia-northeast3-docker.pkg.dev/replace-project/jhworks/web@sha256:<64자리 digest>' \
  --commit '<40자리 SHA>' --output ../../artifacts/cloud-run/public-demo-service.json
uv run pytest tests/test_public_demo_manifest.py tests/test_gateway_boundary.py -o addopts= -q
```

명령은 placeholder를 검증된 실제 값으로 교체한 뒤 사용한다. 로컬 파일만 생성하며 cloud API를 호출하지 않는다.

## 검증과 외부 적용 조건

로컬 관련 20개 통과: manifest 격리/예산/image/SHA 거부, production Settings 해석,
기존 private manifest 불변과 cookie alias를 검증했다. 기존 별도 프로세스의 custom origin HTTP 시나리오에
guest 시작→현재 사용자→역할 전환→피드백→로그아웃을 추가했다. __session 사용, private JWT/공유
비밀번호 로그인 거부, pikan.dev 루트에서의 교차 Origin 쓰기403을 확인한다.
이것은 실제 Firebase proxy/공개 브라우저 쿠키 동작을 대신하지 않는다.
로컬 전체 API415 passed/21 skipped (37.35초), Ruff app/tests/alembic,
strict mypy app/tests151 files 통과. PostgreSQL/전체 브라우저/컨테이너는 이 PR의 CI 결과로 구분한다.

적용 순서:

1. 정확한 PR head CI/리뷰/병합 → 기존 private workflow로 검증된 main 이미지/DB head 확보.
2. 새 jhworks-demo 비공개 서비스·정리 Job의 실제 manifest/digest/참조와 예상 비용을 제시하고 승인받기.
3. 승인 후 생성·guest 업무 리허설·합성 데이터 보존/새 공간 수·정리 dry-run 검증.
4. 공개용 신원/합성 공용 규정·일정/보관 정리 주기/실패 알림과 보관 정책의 운영 조건을 확정.
5. 공개 IAM과 Hosting rewrite는 실제 적용 직전에 별도 승인. 정적 준비 화면용 CSP/default-src none과
   정적 검증 도구를 그대로 실제 Next.js 앱에 사용하지 않는다. 실제 동적 응답/자산별 보안·캐시 계약 검토.
6. custom HTTPS에서 guest 역할/결재/피드백/만료/CSRF/격리 검증 후 별도 포트폴리오의 버튼 연결.

현재 새 서비스/Job·공개 IAM·rewrite·AI 연결은 적용하지 않았다. 실제 도메인은 기존 준비 화면이다.
학습/면접: 앱의 public_demo 플래그와 Cloud Run public IAM이 서로 다른 경계인 이유, Hosting의 쿠키
전달 규칙이 로그인 성공 뒤401을 만드는 과정, 공유 DB와 별도 workload의 권한을 어떻게 검증할지 설명한다.
