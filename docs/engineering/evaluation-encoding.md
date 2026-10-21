# QA-01: 평가 JSON의 인코딩 계약

## 재현과 선택

기준 main `2dfb0d0`에서 한국어 Windows의 Python 3.12를 `-X utf8=0`으로 실행했다.
`approval_review.load_cases()`는 기본 인코딩 cp949에서 UnicodeDecodeError로 실패했다.
JSON 파일은 UTF-8인데 `Path.read_text()`가 운영체제 기본값을 사용했기 때문이다.

전역 환경변수나 모든 개발자 실행 명령에 우회 옵션을 요구하는 대신 파일 계약을 코드에 명시한다.
다섯 평가 dataset과 suite manifest 읽기, suite JSON 결과 저장에 encoding="utf-8"을 지정한다.
suite 자식 Python은 UTF-8 모드로 실행하고 부모의 stdout/stderr 디코딩도 UTF-8로 지정한다.
런타임 API·인증·LLM 설정은 바꾸지 않고 새 패키지도 추가하지 않는다.

## 검증

- 수정 전: cp949 기본 모드에서 approval-review dataset 읽기 실패.
- 수정 후: 같은 명령에서 6개 사례 로딩 성공.
- 새 회귀: UTF-8 모드를 끄고 EncodingWarning을 오류로 처리한 별도 프로세스에서
  다섯 dataset과 manifest를 읽는다. Linux에서도 암묵적 기본 인코딩 사용을 검출한다.
- 별도 합성 Python 모듈의 한국어 JSON 출력을 실제 subprocess로 읽어 suite 결과를 검증한다.
  provider와 network는 호출하지 않는다.
- 관련 테스트 7개, Ruff app/tests/alembic, strict mypy app/tests 109 files 통과.
- 전체 API도 `python -X utf8=0 -m pytest -ra`로 **215 passed / 18.75초**.
  Windows cp949 기본 모드에서 기존 `-X utf8` 실행 우회 없이 통과했다.

운영체제 기본값은 파일 포맷의 일부가 아니다. 면접에서는 파일 읽기뿐 아니라 자식 프로세스의
출력 인코딩과 부모의 디코딩도 일치해야 한다는 점을 이 재현으로 설명할 수 있다.
provider 품질·유료 AI 실험이나 cloud 성능 개선을 검증한 변경은 아니다.
