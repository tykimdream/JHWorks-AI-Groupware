# 입력 이어받기와 공개 브랜드·공유 정보 — 2026-10-25

## M3-02A: AI 실패 → 직접 작성

AI 장애·예산 소진·지원하지 않는 요청 화면에서 직접 작성을 선택하면 최초 요청, 반영된 추가 답변,
아직 반영되지 않은 답변을 순서대로 `업무 내용`에 옮긴다. 원문을 변환하거나 금액·날짜·사용처를
추정하지 않는다. 공개 모드는 경비 유형을 선택하고, 비공개는 확인된 preview 유형이 있을 때만 사용한다.
제목·구조화된 지출 정보는 직접 확인해야 하며 이 이동은 API 저장/제출을 실행하지 않는다.

| 경계 | 동작 |
| --- | --- |
| 명시적 전달 | 버튼으로 `?handoff=manual` 이동. URL에는 업무 텍스트·직원ID를 넣지 않음 |
| 보관 | sessionStorage, 직원ID별 키, 같은 탭, 최대15분 |
| 읽기 | 새 작성 페이지의 명시적 전달에서만 읽고 mount 후 삭제 |
| 일반 새 작성·기존 문서 편집 | 보관 입력을 사용하지 않음 |
| 로그아웃·확인된 계정/역할 변경·현재 세션 만료 | 이전 직원의 대기 중인 수동 전달값 삭제 |
| 저장 차단·공백·5,000자 초과 | 자동으로 잘라내거나 이동하지 않고 원래 화면에 오류와 입력 유지 |
| 만료·잘못된 JSON·다른 계정 | 복원하지 않음. 만료/손상된 현재 키는 삭제 |
| 새 작성 후 새로고침 | 전달값을 이미 소비했으므로 다시 복원하지 않음. 전체 폼 자동 저장은 별도 과제 |

로그아웃 때 기존 home→AI 전달값도 함께 정리한다. 이 저장소는 보안 경계가 아니며,
실제 업무/개인정보 대신 합성 정보로 체험하도록 안내한다. 서버는 기존 권한 검사를 유지한다.
사용성 효과는 구현 가설이며 신규 사용자 실험 결과를 대신하지 않는다.
목록 위치·상세 복귀·편집 중 이동 경고 등의 나머지 M3-02 항목은 아직 미구현이다.

## 로고와 홈 탐색

`BrandLogo`는 [사용자가 승인한 B 워드마크](../design/brand/README.md)의 전체 JHWorks 윤곽을 사용한다.
favicon은 같은 워드마크의 완전한 J를 파생해 사용한다. 두 SVG 원본에서 앱용 윤곽과 SVG 아이콘을 생성하고 CI에서 동기화를 검사한다.
사이드바, 로그인/체험 진입, 피드백, JHW Pattern 상단에서 동일하게 `/`로 연결한다.
스크린 리더 이름은 `JHWorks 홈으로`이며 키보드 focus 링을 제공한다.
비로그인 홈 접근은 기존 인증 흐름에 따라 체험 진입으로 이동한다.
새 UI는 Tailwind와 JHW 토큰을 사용한다. favicon·OG의 고정 색은 현재 primary `#6554cf`와 맞춘다.

## 공유 카드·검색 메타데이터

- 대표 주소는 고정 `https://groupware.pikan.dev`이며 요청 Host나 업무 응답으로 만들지 않는다.
- 기본 한국어 제목·설명과 `og:title`, `og:description`, `og:image`, `og:url`, locale,
  Twitter large image card를 서버 metadata로 제공한다.
- 1200×630 PNG는 Next ImageResponse로 빌드 시 생성한다. 고정 SVG와 영문 브랜드 문구만 사용하며
  외부 폰트 fetch·AI 호출·직원/결재/쿠키 데이터가 없다. 이미지 문구는 제공 중인 모든 AI가 켜졌다고 주장하지 않는다.
- `/login`(공개 체험 소개), `/pattern`만 index/follow와 자기 canonical을 갖고 sitemap에 포함한다.
- 업무 홈·결재·근태·조회·피드백 등은 기본 noindex/follow를 상속한다. 개인별 문서 제목을 OG에 넣지 않는다.
- robots는 HTML 크롤링을 허용해 noindex를 읽게 하고 API만 제외한다. robots를 권한 통제로 사용하지 않는다.
  [Google 공식 noindex 지침](https://developers.google.com/search/docs/crawling-indexing/block-indexing)을 따른다.
- Next 설치 버전의 Metadata·ImageResponse·robots/sitemap 문서를 확인해 구현했다.
  [Metadata 공식 문서](https://nextjs.org/docs/app/getting-started/metadata-and-og-images)도 참고한다.

검색 결과 등록·순위를 보장하지 않는다. Search Console 등록이나 외부 공유 서비스 캐시 갱신은 실행하지 않았다.
공개 배포 전에는 기존 사이트의 카드가 유지된다. 이번 변경은 공개 AI 활성화를 포함하지 않는다.

## 검증 경계

Playwright PC/모바일에서 홈 로고·focus·가로 넘침, 실제 crawler HTML 메타·canonical·noindex,
OG PNG signature/1200×630, sitemap/robots를 검사한다. 전달 회귀는 미저장/일회 소비,
저장 차단, 만료·계정 분리·일반 진입·로그아웃 정리, 추가 답변·한도 초과를 포함한다.
화면·OG 육안 검토 파일은 Git 제외 `artifacts/brand/`에 보관한다.

전체 브라우저 묶음이 분당60회를 넘겨 인증하는 것을 관찰해 격리된 `tests.e2e_server`만
지원 범위 내600회로 설정했다. 실제 limiter·기본60회·공개 비밀번호 로그인 차단은 변경하지 않는다.
