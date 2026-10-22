# 데모 분리 기반 실제 적용 — 2026-10-23

## 승인과 실제 범위

사용자가 Cloud Shell 기존 범위 인증 갱신, 이어서 「분리 기반·제한 권한 적용」을 승인했다.
[PR #48](https://github.com/tykimdream/JHWorks-AI-Groupware/pull/48)의 SQL/profile을 기준으로 적용했다.
코드 head 54374e4의 CI 39802843828은 5개 성공: API426 passed/23 skipped(39.30초),
PG23 passed(7.32초), browser16+2, container-smoke, dependency-review.
자체 리뷰 COMMENT·라벨 후 main 2fa5319에 병합하고 브랜치를 정리했다.

이번 승인은 NOLOGIN DB 역할/schema, GCP 계정 2개·빈 Secret 3개·제한된 읽기/actAs 권한에 한정됐다.
비밀번호·Secret 값 등록, 서비스 업데이트, migration Job 생성/실행, Scheduler, 삭제, 공개는 포함하지 않았다.

## Supabase 실제 결과

기존 Free/Seoul 프로젝트 `uztfgtfvxhpmavybldbh`에서 SQL을 실행했다.
UTF-8/LF 정규화한 `supabase-demo-bootstrap.sql` SHA256:
`48ce18fd705af7aa4c8a166a0648f371e7ca370faaa2a502b15719ebb55812d8`.
실행 전 새 schema/두 역할이 없고 vector가 extensions에 있음을 확인했다. 실행 결과 Success였다.
후속 SELECT의 실제 결과:

| 항목 | 결과 |
| --- | --- |
| groupware_demo 소유자 / 테이블 수 | jhworks_demo_migrate / 0 |
| 새 DB 역할 / LOGIN 역할 / 관리 권한·INHERIT 역할 수 | 2 / 0 / 0 |
| runtime의 demo USAGE / CREATE | true / false |
| runtime·migrate의 private groupware USAGE | 각각 false |
| runtime의 migration 역할 membership | false |
| anon·authenticated의 demo schema USAGE | 각각 false |
| 향후 runtime 테이블 default grants | DELETE,INSERT,SELECT,UPDATE |
| 향후 runtime sequence default grants | SELECT,USAGE |
| 기존 private DB head | f30c9a71b624 |
| 기존 private 직원·결재 | 3 / 2 |
| 기존 리허설 공간·피드백 | 6 / 3 |

행 수와 head가 적용 전후 같음을 확인했다. 새 전체 업무 fingerprint나 backup/restore를 수행했다는
뜻은 아니다. 새 schema에는 아직 Alembic table조차 없으며 원격 migration/실제 역할 로그인을 검증하지 않았다.

## GCP 실제 결과

프로젝트 `jhworks-staging-tykimdream`에 다음을 생성했다.

- 실행 계정 `jhworks-demo-runtime`, `jhworks-demo-migrate`. user-managed key는 각각 0개.
- 빈 Secret `jhworks-demo-runtime-database`, `jhworks-demo-migration-database`, `jhworks-demo-session-secret`.
- runtime은 runtime DB/session, migrate는 migration DB/session의 `secretAccessor`를 갖는다.
  각각 Secret 리소스에 `resource.name.endsWith('/versions/1')` 조건을 사용했다(허용 관계 4개).
- 기존 `jhworks-deploy`에 위 두 계정의 `roles/iam.serviceAccountUser`만 연결했다.

명령 성공 결과와 별도로 policy/version/account/key metadata를 다시 읽어 exact target·role·조건·member를
대조했다. project-wide 새 SA grant 0개, 새 계정의 기존 staging Secret grant 0개를 확인했다.
새 세 Secret의 버전 목록은 모두 빈 배열이다. 기존 세 Secret은 ENABLED version1 그대로다.
이는 없는 version1의 실제 payload 읽기 성공을 검증했다는 뜻은 아니다.

Cloud Shell 보조 결과 `demo-identity-apply-result.json`, `demo-identity-verify-result.json`에는
비밀 값 없이 단계/집계만 저장했다. 독립 조회 결과:

```json
{"status":"passed","dedicatedAccounts":2,"userManagedKeys":0,"emptySecrets":3,"secretAccessBindings":4,"allowedVersion":"1","deployActAsBindings":2,"projectWideGrants":0,"oldSecretGrantsForDemoAccounts":0,"oldVersionsUnchanged":true}
```

기존 staging/demo revision은 모두 75d5e8a98fb2다. 프로젝트·서비스 public binding이 없고 인증된
두 서비스의 readiness HTTP200/ready를 확인했다. 이번에 새 서비스/Job 배포나 실제 credential 변경은 없다.

## 비용과 미완료 gate

[Secret Manager 공식 가격](https://cloud.google.com/secret-manager/pricing)을 2026-10-23 확인했다.
빈 Secret 관리 작업은 과금하지 않는다. 이번에 새 활성 버전은 0개다.
후속 새 버전 3개를 자동 복제로 등록하면 무료 할당 적용 전 저장 비용은 총 $0.18/월 수준이며,
결제 계정 전체의 6개 활성 버전·10,000 access 무료 할당 소비에 따라 달라진다.
읽기 초과·로그·컴퓨팅·전송·세금은 별도다. 계정 전체 실제 청구 총액은 이번에 조회하지 않았다.

다음은 [사용자 직접 실행용 credential 초기 설정](demo-credential-setup.md)이다. 값 등록·LOGIN 활성화와
추가 비용을 승인받고 사용자가 숨김 prompt에 직접 기존 관리자 비밀번호를 입력해야 한다.
그 후 실제 pooler 인증·전용 migration·private 데이터 보존·guest flow 검증까지 완료해야 체크포인트 1을
완료로 표시한다. 현재 domain은 준비 화면이고 기존 서비스는 기존 리허설 참조를 계속 사용한다.
