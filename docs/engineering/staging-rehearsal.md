# 첫 private staging 배포 검증

기준 main: `a1c4b7a58ac0e74fc59464cd6ec311f3d01cee9a` (PR #18 병합).
이 기록의 계획/설정/실제 실행 결과를 구분하며, 공개 demo 배포 증거로 사용하지 않는다.
최신 결과는 아래 **PR #19 병합 후 재실행**이다. private service는 Ready이고 수동 smoke 4개가
통과했으나, CI release는 URL 비교 오류로 실패했다. 두 결과를 구분한다.

## 완료 조건

1. GitHub main의 CI 성공, staging Environment의 main 전용 정책과 명시적 승인 확인.
2. WIF는 고정 repository/owner ID, main ref, staging subject, 해당 workflow_ref를 모두 요구한다.
3. deploy 계정은 전용 프로젝트에서 정의한 Cloud Run 배포/읽기/호출 권한만 갖는다.
   custom role에는 delete, setIamPolicy, SSH, job override 권한이 없다.
   최초 service/job 생성은 parent project 권한이 필요하므로 이 역할의 범위는 전용 프로젝트다.
4. registry writer는 서울 `jhworks` 저장소에만, actAs는 runtime/migrate 두 계정에만 부여한다.
   WIF principal은 deploy 계정만 impersonate한다. key 파일을 만들지 않는다.
5. 새 합성 DB의 schema/role/Secret version은 이미 준비됐다. 실제 app-role 접근과 online migration,
   서비스 준비/TLS/cookie/smoke, 이전 버전 복구 가능 범위를 검증한다. 자동 seed/reset은 하지 않는다.

## 권한의 의미와 대안

`roles/run.developer`는 삭제/SSH 등 이번 release에 필요하지 않은 권한도 포함한다.
`deployer-role.yaml`은 필요한 배포·상태 확인·호출 권한만 명시한다. 새 권한이 필요하면 실제 실패와
공식 문서를 확인한 후 범위를 검토하며 Owner/Editor를 부여해 해결하지 않는다.

배포 계정의 actAs는 두 실행 계정으로 코드를 실행하는 권한이다. 직접 Secret Accessor를 주지 않아도
그 코드가 승인된 Secret을 사용할 수 있으므로 간접 접근 능력이 있다. GitHub repository/main/workflow와
Environment 승인 경계가 중요하다. 실행 계정은 각 DB/session Secret version 1에만 접근한다.

장기 서비스 계정 키는 유출 시 회수까지 사용할 수 있다. WIF는 GitHub의 짧은 수명 OIDC token을 검증해
한정된 계정 권한으로 교환한다. 이 조건은 서명·issuer/audience 검증을 대체하지 않으며 함께 적용된다.

## 현재 확인

- PR #18 merged, 로컬 main 동기화 완료.
- main push CI [39571926731](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39571926731) 성공.
- 사용자 승인으로 custom role 27개 permission, 전용 registry writer, 두 실행 계정 actAs,
  WIF pool/provider와 deploy 계정 impersonation binding을 적용했다. provider ACTIVE/조건을 재조회했다.
- staging Environment는 owner reviewer 1명과 main 전용 branch 정책을 사용한다. 1인 프로젝트라
  self review를 허용한다. repository variable 5개를 설정했고 CD flag를 true로 전환했다.
  workflow 자체는 수동 dispatch만 허용한다. main push 자동 배포는 아직 없다.
- SQL Editor에서 배포 직전 `groupware` 업무 table 수 0을 확인했다. 첫 bootstrap의
  `fresh-synthetic-db:groupware-table-count-0:2026-10-21:sql-editor-verified` 참조는 빈 DB 확인이며
  backup/restore 실험 결과가 아니다.
- 최초 run [39573659876](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39573659876)의
  attempt 1은 exact main CI/설정 검증 후 WIF attribute condition에서 거부됐다. 이미지 생성,
  migration, service rollout은 실행되지 않았다. 사용자가 Environment 승인을 직접 수행했다.
- GitHub REST `GET /repos/tykimdream/JHWorks-AI-Groupware/actions/oidc/customization/sub`에서
  `use_default=true`, `use_immutable_subject=true`, prefix
  `repo:tykimdream@53204415/JHWorks-AI-Groupware@1341433132`를 확인했다.
  저장소는 2026-08-21 생성됐으며, 이전 형식의 subject 조건이 원인이었다.
- provider의 subject를 위 prefix + `:environment:staging`으로 교정했다. repository/owner ID,
  main, workflow_ref 제한은 그대로다. 서비스 계정 역할을 추가하거나 다른 저장소를 허용하지 않았다.
  같은 run의 실패 job을 재실행했고 사용자가 attempt 2의 Environment 승인도 완료했다.
- attempt 2에서 exact main CI, 설정 검증, WIF authentication, gcloud setup,
  Artifact Registry 인증과 web/API build/push를 실제 GitHub runner에서 통과했다.
- API index digest: `sha256:e391052dc7dadc62b9a0f3610f3e95d27a2cd3c5a80550372784720df39848ab`.
  Web index digest: `sha256:658f19d06d0dfa59c3403cce38a80f00eab3ddd8575e3eb042402b1113ca8832`.
  두 SHA tag와 digest를 Artifact Registry 목록에서도 확인했다.
- attempt 2는 service 조회에서 `CalledProcessError`로 중단됐다. CI release artifact를 내려받아
  status/errorType/commit을 확인했다. Job/service 생성이나 migration 실행은 없었다.
  Cloud Shell에서 동일 `gcloud run services describe ... --format=json` 명령을 재현하면
  `Cannot find service [jhworks-staging]`가 반환된다. 기존 코드는 stderr의 `NOT_FOUND`에만 의존했다.
  `services list --format=json`은 성공하며 `[]`를 반환했다. migration Job도 존재하지 않았다.
- 외부 migration/rollout/smoke/rollback 성공은 아직 주장하지 않는다.

## 첫 bootstrap 수정과 로컬 검증

`cloud_run_release.py`는 regional service 목록 JSON에서 정확한 이름으로 존재 여부를 판단한다.
서비스가 없으면 명시적 bootstrap만 허용하고, 있으면 기존 describe/IAM/traffic 보호를 그대로 수행한다.
영문 stderr 구문을 추가로 허용하는 대안보다 구조화된 성공 응답을 사용했다. IAM/네트워크 오류나
잘못된 JSON 구조는 실패로 전파하므로 bootstrap flag가 보호 장치를 우회하지 않는다.
목록 조회 권한은 기존 승인된 custom role에 포함돼 있어 새 IAM grant가 필요하지 않다.

| 검증 | 결과 |
| --- | --- |
| 배포 회귀 테스트 | 29 passed: bootstrap, 기존 traffic/rollback/public IAM 경계, discovery 오류/형식 검증 |
| 전체 API | 190 passed, Windows UTF-8 실행, 외부 LLM 호출 없음 |
| Ruff | app/tests 전체 통과 |
| strict mypy | 106 source files 통과 |
| 실제 cloud CLI | service describe 부재 오류와 성공한 빈 목록을 재현 |

로컬 Docker 엔진은 사용할 수 없어 수정 커밋의 image/Compose smoke는 GitHub CI에서 재검증해야 한다.
web 소스는 바꾸지 않았으며 이번 수정에서 web build/E2E는 다시 실행하지 않았다. PR #18의 기존 성공
기록과 이번 로컬 검증을 구분한다. WIF bootstrap script는 Bash syntax check를 통과했고 role/condition
JSON/YAML을 정적 검사했다. 실제 잘못된 repo 토큰을 제출하는 음성 인증 실험은 별도 미검증이다.

## 재현 및 다음 작업

### PR #19 병합 후 재실행 — 2026-10-21

- [PR #19](https://github.com/tykimdream/JHWorks-AI-Groupware/pull/19)의 head
  `8cbb61b11a871c99d7ffedc188235ed420117aee`는
  [CI 39575645123](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39575645123)에서
  validate/browser/container-smoke/dependency-review 네 작업을 모두 통과했다.
- 사용자 병합 후 main `dfff250e6209c93860e26bc0a1c2a40e46663804`를 fast-forward로 동기화했다.
  [main CI 39576572797](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39576572797)는
  성공했다. push 이벤트의 dependency-review는 workflow 조건에 따라 skipped다.
- SQL Editor에서 `groupware_table_count=0`을 다시 확인했고, 서울 Cloud Run service/job 목록도
  둘 다 `[]`임을 확인했다. 기존 DB/이미지/자원은 삭제하지 않았다.
- 새 SHA의 [staging run 39577006110](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/39577006110)을
  bootstrap으로 dispatch했다. backup reference는
  `fresh-synthetic-db:groupware-table-count-0:2026-10-21:sql-editor-reverified:dfff250`다.
  사용자가 Environment 승인을 직접 완료한 뒤 image/migration/service 배포를 실행했다.
- 이 배포는 기존 승인된 private staging 범위다. public IAM/유료 DB/AI 연결을 추가하지 않는다.

#### 실제 cloud 결과

| 확인 | 결과 |
| --- | --- |
| API image | `sha256:6763d6609a12811d084fab4bbe63d83e3e2f8768e6fa1da1159b893563ab637e` |
| Web image | `sha256:42ea8d4cc9b78af841f402af43a2b09a878787a6d7bbf2b8481feb17797acdf3` |
| migration 실행 | `jhworks-staging-migrate-tj9v2`: Completed=True, succeededCount=1, 12.17초 |
| 실제 DB | Alembic head `b63d91e52fa0`, groupware table 11개 |
| DB 권한 조회 | runtime USAGE=true/CREATE=false/DML=true, anon/authenticated USAGE=false |
| service revision | `jhworks-staging-dfff250e6209`, Ready=True, traffic 100% |
| private IAM | invoker check 활성, service public binding 없음, project public binding 없음 |
| 인증 없는 외부 GET | deterministic URL과 hash URL 둘 다 403 |
| 별도 수동 smoke | 2026-10-21 18:33 KST, liveness/readiness/web 200, 앱 무인증 업무 API 401: 4/4 passed |
| 비용 설정 | min=0/revision max=2 유지. 기본 service max=10을 발견해 승인 범위인 service max=2로 낮추고 재조회 확인 |
| CI release record | failed/application/ValueError/no_previous_revision. GitHub artifact 원본도 로컬 보존 |

수동 smoke는 기존 `deployment_smoke.py`를 Cloud Shell에 저장소와 같은 디렉터리 깊이로 배치해
실행했다. 로그인한 사용자 계정의 짧은 수명 ID token은 subprocess stdout에서 메모리로만 받아
자식 프로세스 환경으로 전달했고 출력하지 않았다. 인증된 Cloud Run 호출 안에서 앱 미로그인 API의
401도 확인했다. 이 검증은 deploy SA의 WIF audience token smoke 성공을 증명하지 않는다.
Cloud Shell 검증 도구의 최초 standalone 경로 실행은 `__file__.parents[4]` 때문에 실패했으며,
저장소 경로 구조에 맞춰 재배치한 후 위 검증에 성공했다. 서비스 장애가 원인은 아니었다.

DB의 권한 함수 조회 결과와 실제 DDL 거부 실행 테스트는 구분한다. 후자는 남아 있다.
위 실행 시간·한 번의 HTTP latency는 부하/성능 benchmark나 개선율 근거로 사용하지 않는다.
seed/reset/데모 로그인/업무 저장은 실행하지 않았고, 실제 사용자/조직 데이터도 넣지 않았다.

#### URL 검증과 비용 제한 수정

실제 `status.url`은 `https://jhworks-staging-ti3vflu2vq-du.a.run.app`이었다.
GCP가 반환한 `run.googleapis.com/urls`에는 위 URL과 설정한
`https://jhworks-staging-968398406137.asia-northeast3.run.app`가 모두 들어 있었다.
설정 URL은 실제 정상 endpoint지만 기존 단일 문자열 비교가 이를 거부했다.

수정은 status URL과 다를 때 **동일 서비스의 GCP 응답에 포함된 URL 목록에서 정확히 일치**하는지만
확인한다. origin 설정을 hash URL로 변경하거나 prefix/suffix 기반으로 임의 URL을 허용하지 않는다.
허용한 origin을 그대로 OIDC audience/HTTP smoke/서버 CSRF 기준으로 사용한다. 누락/잘못된 JSON/
다른 origin은 실패로 남기며 이전 traffic 복구 경로를 유지한다.
service manifest에는 revision max 외에 `run.googleapis.com/maxScale`도 명시해 서비스 전체 최대값을
2로 유지한다. live service의 해당 값도 `gcloud run services update --max=2`로 맞췄다.
이는 청구액 hard cap이 아니며 Cloud Run은 일시적으로 인스턴스 제한을 초과할 수 있다.

로컬 검증: 전체 API **197 passed / 14.72초**, 배포 회귀 **36 passed**, Ruff app/tests 통과,
strict mypy 106 source files 통과. URL 별칭 정상 흐름과 잘못된 목록/외부 prefix origin 거부,
실패 시 rollback을 검증했다. service max 검증은 기존 manifest 테스트에 추가했다.
이번 수정 커밋의 GitHub CI와 WIF 인증 smoke는 아직 실행하지 않았다.

#### 별도 공개 gate

PR #19 준비 중 GitHub Dependabot open 경고 10건(Critical 1, High 6, Medium 3)을 확인했다.
certifi, Mako, braces, brace-expansion, js-yaml의 사용 경로와 패치 가능성을 공개 전에 검증한다.
dependency-review 성공은 기존 경고가 해결됐다는 의미가 아니다. 아직 실제 exploit을 재현한 것은 아니다.

OIDC 오류가 발생하면 먼저 repo OIDC customization metadata와 provider 조건을 비교한다.
JWT 전체나 access token은 출력하지 않는다. 2026-07-15 이후 신규 저장소는 immutable subject가
기본이므로, 이름만 들어간 예전 예제를 그대로 복사하면 인증이 거부된다. subject 조건을 삭제해
해결하면 Environment 경계가 사라질 수 있다. 이 저장소는 정확한 immutable subject를 요구한다.
의도적으로 다른 repo/ref/environment 토큰을 제출하는 음성 실험은 아직 수행하지 않았다.

다음은 URL/최대 인스턴스 수정 커밋을 승인받아 push/PR/CI/병합하고, DB backup/restore 근거를
확보한 뒤 **새 main SHA**의 일반 release를 실행하는 것이다. DB와 service가 이미 존재하므로
bootstrap은 사용하지 않는다. 현재 비공개 서비스는 유지하며 실패한 CI를 성공으로 바꾸어 기록하지 않는다.
기존 SHA image tag는 immutable하므로 동일 run을 무조건 다시 build/push하지 않는다. 기존 이미지나
자원을 삭제하지 않는다. 현재 head의 업무 schema를 빈 DB로 간주하거나 fresh-DB reference를 재사용하지 않는다.
migration에 실패하면
서비스 rollout을 중단하고 DB를 삭제하거나 downgrade하지 않는다. 첫 release 성공 후에도 실제
업무 smoke, runtime DDL 거부, backup/restore와 application rollback drill은 별도 증거가 필요하다.
공개 데모는 방문자 격리/요청 제한 검증과 공개 IAM 승인 후 진행한다. AI는 계속 비활성이다.

## 근거

- [Google WIF deployment pipelines](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)
- [Cloud Run deployment permissions](https://docs.cloud.google.com/run/docs/reference/iam/roles#deployment_permissions)
- [GitHub immutable subject claims](https://docs.github.com/en/actions/reference/security/oidc#immutable-subject-claims)
- [Cloud Run의 두 URL 형식](https://docs.cloud.google.com/run/docs/triggering/https-request)
- [개발자 private 서비스 인증](https://docs.cloud.google.com/run/docs/authenticating/developers)
- [서비스 전체/리비전별 최대 인스턴스](https://docs.cloud.google.com/run/docs/configuring/max-instances)
