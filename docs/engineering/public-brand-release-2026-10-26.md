# 브랜드·파비콘 실제 반영 — 2026-10-26

공개 앱의 기존 `/favicon.ico`·`/icon.svg`는404였고 HTML에 icon link가 없었다. 로고·OG를 포함한 웹 소스와 실제 배포가 달랐기 때문이다. PR #95를 전체 CI·자체 리뷰 후 병합하고 웹 이미지를 고정 소스로 배포했다.

| 항목 | 확인한 결과 |
| --- | --- |
| 웹 소스 | `cb26b8806ddabb6459eec7de17b7b24b348a85ff` / PR #95 |
| main CI | [40209112610](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/40209112610), success |
| 웹 digest | `sha256:d1d29da918fd3557dfff3ebbd69a3896d07d3cacaff7a92e77509a454ce2be22` |
| 후보 revision | `jhworks-demo-web-cb26b8806dda`, 생성 시0% traffic |
| 이전 revision | `jhworks-demo-b9831c712a2e-91375fe81f8a` |
| API 유지 | `b9831c7` 기반 / `sha256:5828c072c39d1803a5578de3234ce2ee914cb2fb4a5003f379c4f4f24210b8ca` |
| Storybook | [Pages40209766258](https://github.com/tykimdream/JHWorks-AI-Groupware/actions/runs/40209766258), 같은 소스 배포 성공 |

웹 컨테이너의 image 외 필드·API 컨테이너 전체·runtime spec을 배포 전과 대조해 같음을 확인했다. AI=false, concurrency4, revision/service max1도 확인했다. API 교체·DB migration·키 업로드·AI 활성화는 하지 않았다. 웹의 UI·입력 보호·공통 폼·브랜드/공유 메타데이터가 함께 반영되는 웹 버전이다. 모든 main 기능이 API까지 배포됐다고 해석하지 않는다.

## 검증과 실행 경계

- 현재 공개 API 소스 `b9831c7`을 별도 `/tmp`에 추출하고 새 production 웹과 연결했다. 합성 SQLite/fake provider 기반 PC·모바일 public-demo10개 통과. 실제 기업 DB나 유료 모델은 사용하지 않았다.
- Cloud Shell에서 웹 이미지를 빌드했다. Docker push의 연결 거절이 두 번 발생해 공식 `google/go-containerregistry/cmd/crane@v0.22.1`로 동일 이미지·동일 Artifact Registry에 전송했다. 라이브러리·생성 키·IAM 확대는 없다.
- 후보0%에서 SVG/ICO/Apple 원본 bytes 일치·OG1200×630·live/ready200을 확인했다. 후보 구성 대조 후 명시적 revision100% 전환과 임시 favicon tag 제거 명령을 실행했다.
- 전환 후 [실제 도메인의 읽기 점검 원본](evidence/public-brand-2026-10-26.json)에서 세 아이콘의200·원본 SHA256 일치·HTML link·OG·live/ready200을 다시 확인했다. 도메인에서 새 웹이 제공됨을 검증했다.
- Cloud Shell의 최종 traffic 명령 출력은 브라우저 도구가 비활성화되어 재조회하지 못했다. 새 웹의 실제 응답을 확인한 사실과 control-plane 최종 traffic 비율 재확인은 구분한다.
- Storybook 공개 smoke에서도 PC·모바일의 favicon 응답과 link가 같은 앱 원본을 가리키는지 통과했다. 캐시가 남은 기존 탭은 새로고침이나 탭 재열기가 필요할 수 있다.

재현: `node tools/check-public-brand.mjs`는 실제 도메인의 아이콘·공유 메타·health만 읽는다. 업무 세션·방문 공간을 생성하지 않고 AI 호출·업무 쓰기를 하지 않는다. `node tools/check-pattern-pages.mjs`는 별도 정적 문서의 대표 흐름을 확인한다.

복구가 필요하면 이전 revision을 명시한 `gcloud run services update-traffic`로 트래픽을 되돌리고 동일 읽기 점검을 수행한다. DB rollback은 이 웹 단독 변경에 포함되지 않는다. 실제 유료 모델/원격 migration/자동 정리는 별도 적용 조건을 유지한다.
