# 첫 private staging 배포 검증

기준 main: `a1c4b7a58ac0e74fc59464cd6ec311f3d01cee9a` (PR #18 병합).
이 기록의 계획/설정/실제 실행 결과를 구분하며, 공개 demo 배포 증거로 사용하지 않는다.

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

OIDC 오류가 발생하면 먼저 repo OIDC customization metadata와 provider 조건을 비교한다.
JWT 전체나 access token은 출력하지 않는다. 2026-07-15 이후 신규 저장소는 immutable subject가
기본이므로, 이름만 들어간 예전 예제를 그대로 복사하면 인증이 거부된다. subject 조건을 삭제해
해결하면 Environment 경계가 사라질 수 있다. 이 저장소는 정확한 immutable subject를 요구한다.
의도적으로 다른 repo/ref/environment 토큰을 제출하는 음성 실험은 아직 수행하지 않았다.

다음은 수정 커밋을 승인받아 push/PR/CI/병합한 뒤 **새 main SHA**로 bootstrap을 실행하는 것이다.
기존 SHA image tag는 immutable하므로 동일 run을 무조건 다시 build/push하지 않는다. 기존 이미지나
자원을 삭제하지 않는다. DB가 여전히 빈 합성 DB인지 재확인한 후 bootstrap reference를 사용한다.
migration에 실패하면
서비스 rollout을 중단하고 DB를 삭제하거나 downgrade하지 않는다. 첫 release 성공 후에도 실제
업무 smoke, runtime DDL 거부, backup/restore와 application rollback drill은 별도 증거가 필요하다.
공개 데모는 방문자 격리/요청 제한 검증과 공개 IAM 승인 후 진행한다. AI는 계속 비활성이다.

## 근거

- [Google WIF deployment pipelines](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)
- [Cloud Run deployment permissions](https://docs.cloud.google.com/run/docs/reference/iam/roles#deployment_permissions)
- [GitHub immutable subject claims](https://docs.github.com/en/actions/reference/security/oidc#immutable-subject-claims)
