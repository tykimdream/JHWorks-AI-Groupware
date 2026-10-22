# 별도 데모 서비스의 비공개 리허설 — 2026-10-22

## 목적과 완료 조건

기존 private staging을 공개 모드로 덮지 않고, 실제 Cloud Run/PostgreSQL에서 방문자 격리·결재·피드백과
정리 runner의 실행 가능성을 검증한다. 인터넷 공개, 예약 삭제, 실제 만료 데이터 삭제는 이번 범위가 아니다.
사용자는 별도 서비스와 Job, 기존 runtime DB/session Secret v1 재사용, 합성 업무·피드백,
정리 dry-run 1회를 승인했다. 새 Cloud Shell 인증도 같은 범위로 갱신했다.

## 실제 적용

- 프로젝트 `jhworks-staging-tykimdream`, 리전 `asia-northeast3`.
- Service `jhworks-demo`, revision `jhworks-demo-75d5e8a98fb2`.
- Job `jhworks-demo-maintenance`, 실행 `jhworks-demo-maintenance-n544m`.
- 이미지 소스 `75d5e8a98fb2919e46958f7d580b0aa287ed3705`.
  #45 runner는 이미지에 포함된다. #46 offline generator는 제어 측 코드이며 해당 이미지에 포함됐다는 뜻이 아니다.
- API digest `sha256:f2c2a591add033bda6f5019977f5b52cccbfdd92b1bd00ed86109eb579c274f0`.
- web digest `sha256:307dd6e9c9a59225adc465c0b17bc8e7bfeffea0b1ab867636dabd9252bedf12`.
- 기존 staging도 [release 39771645700](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39771645700)
  성공, smoke 4/4, ready revision `jhworks-staging-75d5e8a98fb2`를 확인했다.
- DB head는 기존 `f30c9a71b624`이며 이번 작업에 새 migration은 없다.

적용 manifest SHA-256은 다음과 같다. 비밀 값 없이 이미지·환경 설정·Secret 참조만 담는다.

| 파일 | SHA-256 |
| --- | --- |
| public-demo-service.json | cb2499fd53351bb8a0453b395881b1affdcbdd2ab75f712d5dfb78a010aa4bba |
| demo-maintenance-dry-run.json | 6b7dab05333abdf1433d7f0c84f2e12416e542f04458e4c0c3f2114ff99d4a5d |

브라우저 파일 업로드가 지연·실패해 gzip/base64로 비밀 없는 파일을 전달하고, 원본 SHA와 일치한 뒤 적용했다.
실패한 업로드 동안에는 새 자원을 생성하지 않았다. Cloud Shell 정상 연결 후 이름 충돌이 없음을 먼저 확인했다.

## 실제 검증 결과

Service/project IAM에서 `allUsers`, `allAuthenticatedUsers`가 없고 invoker IAM check가 활성화돼 있다.
인증 없는 HTTP 요청은 403이다. 서비스 전체 및 revision max=1, min=0, concurrency=4,
AI=false, public-demo=true, `__session`을 확인했다. Runtime DB와 session Secret만 version 1로 참조한다.
Job은 retry=0, timeout=120초이며 `--apply`가 없다.

GCP identity token은 메모리에서만 얻어 Authorization header에 사용했다. 쿠키도 메모리 CookieJar에만
보관했다. 토큰·쿠키·비밀번호·DB URL을 출력하거나 URL에 넣지 않았다. HTTP probe는 Python 표준
라이브러리를 사용했고 canonical run.app URL에 요청하면서 쓰기 Origin은 `https://groupware.pikan.dev`로 설정했다.

| 실제 HTTP 시나리오 | 결과 |
| --- | --- |
| 공개 모드 configuration, 방문자 시작, me | 각각 200, enabled=true, 같은 직원 ID |
| 세션 | `__session`, Secure, HttpOnly 확인 |
| 루트 포트폴리오 Origin으로 역할 변경 | 403 |
| 일반 결재 작성 → 상신 → 결재자 전환 → 승인 | 201 → 200 → 200 → 200, APPROVED |
| 피드백 제출·동일 내용 재전송 | 200, 같은 응답 ID |
| 피드백 공개 GET | 405 |
| 두 번째 방문자 | 다른 department ID |
| 다른 workspace 결재 상세 접근 | 403 |
| 로그아웃 → me | 200 → 401 |

최종 실행 15개 HTTP 확인이 passed였다. 최초 probe는 접근 거부를 404로 잘못 기대해 실패했다.
기존 서버의 AuthorizationError/403 계약을 확인하고 probe를 수정했다. 수정 전달 중 문자열 문법 오류로
기존 probe가 한 번 더 실행됐다. 최종 실행을 포함해 합성 공간 6개·승인된 일반 결재 3건·피드백 3건을
생성했다. 최종 실행의 생성량(2/1/1)을 전체 생성량으로 혼동하지 않는다. 이 기록은 브라우저 UI E2E나
기존 private 업무 테이블의 새 fingerprint 비교를 수행했다는 증거는 아니다.

Job 실행은 2026-10-22 13:14:04.564190Z~13:14:16.766341Z, succeededCount=1이었다.
실행 이름으로 제한한 실제 Cloud Logging JSON 결과:

```json
{"dryRun":true,"stage":"complete","status":"passed","steps":{"feedback":{"expired":0,"removed":0,"stored":3},"workspaces":{"planned":0,"removed":0}}}
```

만료 대상이 0개였으므로 실제 만료 행 삭제나 30일 경과 운영을 검증했다고 주장하지 않는다.
삭제/동시성/부분 실패/재시도 동작의 자동 검증은 [runner 문서](demo-maintenance-job.md)의 CI와 구분한다.

## 재현 경로와 비용 경계

[Service generator](public-demo-service.md)와 [Job generator](demo-maintenance-job.md)로 성공한 release의
immutable digest를 사용해 명세를 만든다. 이름 충돌·이미지·Secret 참조·IAM을 확인한 뒤 승인된 환경에서 적용한다.
리허설용 Secret 참조를 실제 공개 서비스의 권장 구성으로 해석하지 않는다.

```sh
gcloud run services replace "$HOME/public-demo-service.json" \
  --project=jhworks-staging-tykimdream --region=asia-northeast3 --quiet
gcloud run jobs replace "$HOME/demo-maintenance-dry-run.json" \
  --project=jhworks-staging-tykimdream --region=asia-northeast3 --quiet
gcloud run jobs execute jhworks-demo-maintenance \
  --project=jhworks-staging-tykimdream --region=asia-northeast3 --wait --quiet
```

실제 실행은 1회다. 위 명령은 문서 확인만으로 재실행하지 않는다. HTTP probe를 재실행하면 합성 행과
일일 시작 예산이 추가로 소비된다. Cloud Shell home의 `demo-rehearsal-http.py`와 결과 JSON은 세션 보조
산출물이며 저장소 CI를 대체하지 않는다.

이번 승인 때 추가 컴퓨팅 $0~$0.10를 목표로 추정했다. 실제 청구 총액은 조회하지 않았다.
최소 인스턴스 0은 무과금 보장이 아니며 시작·요청·Job·로그·전송·계정 공유 무료 할당이 영향을 준다.
Job 실행 시간 약 12.2초는 최소 1분 과금 단위를 낮추지 않는다. 5천원/1만원 예산 알림도 과금 차단이 아니다.
예약 작업은 만들지 않았고 현재 Job은 수동 dry-run이다.

## 공개 전 남은 gate

1. 공개 서비스 전용 runtime 신원, session key, DB 권한/schema 분리안을 준비·검증한다.
   현재 공유 runtime/session 참조는 승인받은 비공개 리허설 범위다. 새 권한·인증정보는 별도 확인한다.
2. 합성 공용 규정·일정과 방문자 화면, 접근성·모바일·오류 복구를 실제 브라우저에서 검증한다.
3. 피드백 30일 보관 약속을 지키는 주기 실행과 실패/성공 누락 감지를 마련한다.
   Scheduler 생성·추가 호출 신원·실제 삭제 활성화는 승인 전 수행하지 않는다.
4. Firebase Hosting rewrite, CSP/cache, `__session`, private URL 우회/공개 IAM 범위를 검토한다.
   공개 전환 승인 후 실제 custom domain E2E를 통과해야 라이브 데모로 표시한다.
5. 포트폴리오 라이브 데모·피드백 진입점을 연결하고 변경/피드백 반영 이력을 남긴다.

현재 `groupware.pikan.dev`는 HTTPS 준비 화면이다. 기존 private staging, AI 꺼짐, 루트 포트폴리오,
DNS/Hosting rewrite는 이번 리허설로 변경하지 않았다.
