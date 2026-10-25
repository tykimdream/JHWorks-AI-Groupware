# 실제 소비 폼·상태 컴포넌트 — M4-01

## 추출 범위

`@jhworks/pattern/react`에 Field, Input, Select, Textarea, Alert, EmptyState, ConfirmationDialog를 추가했다. 예제 전용 복사본이 아니라 경비 폼·서버 오류·빈 결재 목록·제출/승인/반려/재작성과 입력 이동 확인이 소비한다. `/pattern`도 같은 export로 실제 조작 예제를 제공한다.

Field는 한 native control의 id·라벨·설명·오류를 연결한다. 각 입력은 기본·invalid·disabled·focus·required와 ref/이벤트를 유지한다. 기존 입력 전체를 한 번에 바꾸지 않고 대표 경비·제목/내용부터 이전한다. 사업부별 폼 상태·저장·권한·navigation guard는 앱에 남긴다.

ConfirmationDialog는 읽기 전용 본문과 두 결정 버튼에 한정했다. 입력 모달 전체를 지원한다고 일반화하지 않는다. 제품의 이전 dialog CSS는 제거하고 패키지의 의미 토큰·namespace CSS로 옮겼다. 본문의 금액/의견 표시는 앱의 업무 표현이며 패키지에 넣지 않는다.

## 상태와 접근성 계약

- 라벨은 화면에 표시하고 native control과 연결한다. 필수 표시는 스크린리더 이름을 바꾸지 않고 native required를 사용한다.
- 오류 텍스트와 입력을 aria-describedby/aria-invalid로 연결한다. 소비자의 추가 설명도 유지한다.
- disabled와 저장 중 입력 잠금, 오류 시 기존 입력 유지, 버튼의 기본 type=button을 유지한다.
- Alert는 실패/정보/성공을 색과 역할·글자로 구분한다. EmptyState는 로딩/실패를 정상 빈 결과로 표시하지 않는다.
- 확인 창은 취소 초기 포커스·Esc 취소·Tab 순환·트리거 복원과 busy 중 이탈 차단을 공유한다.
- 현재 패키지는 private이며 UNLICENSED다. npm 게시/라이선스 확정은 이번 범위가 아니다.

## 검증

기존 package check·웹 TypeScript·빌드와 제품의 입력 보호·보완·실제 저장/제출/승인 회귀를 실행한다. `e2e/pattern-components.spec.ts`는 PC/모바일에서 라벨/설명/오류 연결, 조작과 무API쓰기, 대화상자 포커스/취소/확인, 화면 넘침을 검사한다.

Storybook은 다음 M4-02에서 동일 export를 사용해 상태별 stories와 독립 소비 환경으로 검증한다. 이 PR의 Pattern 페이지를 Storybook 배포라고 표현하지 않는다.
