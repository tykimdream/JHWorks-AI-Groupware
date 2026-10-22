# 공개된 로컬 fixture의 원격 DB 오사용 차단

## 문제와 범위

기존 seed는 README에 공개된 demo1234로 합성 계정을 만든다. 로컬 개발·기존 API/E2E의 fixture로는
유용하지만 원격 DB에서도 같은 함수를 실행할 수 있었다. cloud 배포 workflow는 seed를 실행하지 않는다.
이번 수정은 알려진 비밀번호를 바꾸거나 실제 계정을 만드는 작업이 아니라 해당 fixture의 실행 경계다.

## 선택과 검증 기준

`seed_database`의 첫 SQL 이전에 환경과 실제 SQLAlchemy bind URL을 함께 확인한다.
development/test와 SQLite 또는 localhost/loopback/로컬 Compose db의 PostgreSQL만 허용한다.
staging/production/알 수 없는 환경과 원격 PostgreSQL은 거부한다. 환경변수 하나만 검사하면
development 오설정 상태의 원격 DB를 막지 못하므로 실제 bind도 함께 확인한다.
로컬 Compose의 db는 로컬 개발용 이름이라는 전제이며 임의 DNS 변조까지 증명하는 경계는 아니다.

연결이 열리면 실패하는 SQLAlchemy hook으로 production/staging/preview/원격 주소를 검사한다.
거부 경로에서는 SQL·connection·credential 생성이 없어야 한다. 기존 전체 업무 테스트의 로컬 fixture는
통과해야 한다. 실제 Supabase 쓰기·계정 생성·비밀번호 변경은 수행하지 않는다.

private staging 검증 계정은 별도 작업에서 프로젝트·비공개 IAM·빈 업무 DB·백업을 확인하고
공개 기본값을 사용하지 않는 방식으로 준비해야 한다. 실제 인증정보 설정 전 사용자 확인이 필요하다.

## 실행 결과

원격/환경 거부 테스트 5개, QA-01이 반영된 전체 API **220 passed / 18.41초**
(`python -X utf8=0 -m pytest -ra`), Ruff app/tests/alembic,
strict mypy app/tests 110 source files 통과. 실제 로컬 PostgreSQL Compose seed는 PR container-smoke로
검증하며 외부 DB에 이 함수를 실행해 보지는 않는다.
