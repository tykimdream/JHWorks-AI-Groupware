'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { tokens } from '@jhworks/pattern';
import { Badge, Button } from '@jhworks/pattern/react';
import { ContextHint } from '@/components/context-hint';

function CodeSample({ name, code }: { name: string; code: string }) {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);
  return (
    <details className="pattern-code">
      <summary>코드 보기 · {name}</summary>
      <pre>
        <code>{code}</code>
      </pre>
      <Button
        variant="secondary"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(code);
            setCopied(true);
            setFailed(false);
          } catch {
            setFailed(true);
          }
        }}
      >
        코드 복사 · {name}
      </Button>
      <span role="status">
        {copied ? '복사했습니다.' : failed ? '코드를 선택해 직접 복사해 주세요.' : ''}
      </span>
    </details>
  );
}
const components = [
  {
    id: 'button',
    name: 'Button',
    label: '버튼',
    summary: '한 영역에 주요 행동 하나를 두고, 버튼 이름에 결과가 드러나게 씁니다.',
  },
  {
    id: 'badge',
    name: 'Badge',
    label: '상태',
    summary: '색상과 함께 상태를 글자로 표시합니다. 배지는 행동을 실행하지 않습니다.',
  },
  {
    id: 'hint',
    name: 'ContextHint',
    label: '도움말 툴팁',
    summary:
      '짧은 보충 설명만 담습니다. 필수 입력 조건과 오류 해결 방법은 화면에 직접 보여 주세요.',
  },
];

export function PatternLibrary() {
  const [query, setQuery] = useState('');
  const [clicked, setClicked] = useState(false);
  const search = useRef<HTMLInputElement>(null);
  const matches = (value: string) => value.toLowerCase().includes(query.trim().toLowerCase());
  const foundTokens = tokens.filter((token) =>
    matches(`${token.name} ${token.group} ${token.description}`),
  );
  const foundComponents = components.filter((item) =>
    matches(`${item.name} ${item.label} ${item.summary}`),
  );
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        search.current?.focus();
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  return (
    <div className="pattern-site">
      <a className="pattern-skip" href="#pattern-main">
        본문으로 건너뛰기
      </a>
      <header className="pattern-header">
        <Link href="/pattern" className="pattern-logo">
          <span>jhw.</span> Pattern
        </Link>
        <Badge>0.1 · Workspace preview</Badge>
        <Link href="/">JHWorks로 돌아가기 ↗</Link>
      </header>
      <div className="pattern-layout">
        <aside className="pattern-nav">
          <label htmlFor="pattern-search">
            패턴 검색 <kbd>⌘ K</kbd>
          </label>
          <input
            id="pattern-search"
            ref={search}
            type="search"
            value={query}
            placeholder="색상, 간격, Button…"
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Escape') setQuery('');
            }}
          />
          <nav aria-label="패턴 문서">
            <a href="#start">시작하기</a>
            <a href="#principles">디자인 원칙</a>
            <a href="#tokens">디자인 토큰</a>
            <a href="#components">컴포넌트</a>
            <a href="#workflow">업무 패턴</a>
            <a href="#accessibility">접근성·기여</a>
          </nav>
          <p>실제 제품과 같은 패키지를 사용합니다.</p>
          <a href="https://github.com/tykimdream/JHWorks-AI-Groupware/tree/main/packages/pattern">
            GitHub 소스 ↗
          </a>
        </aside>
        <main id="pattern-main" className="pattern-main">
          <section id="start">
            <p className="eyebrow">JHWORKS PATTERN</p>
            <h1>
              좋은 업무 흐름을 만드는
              <br />
              작은 규칙들.
            </h1>
            <p className="pattern-lead">
              색상 이름에서 확인 버튼의 문구까지. JHWorks에서 실제로 사용하는 디자인 토큰과
              컴포넌트, 그리고 선택의 이유를 기록합니다.
            </p>
            <div className="pattern-notice">
              <strong>현재는 workspace 미리보기입니다.</strong>
              <p>
                npm에는 아직 배포하지 않았습니다. 토큰과 Button·Badge를 로컬 패키지로 소비하며,
                ContextHint와 업무 가이드는 제품에서 검증 중인 패턴입니다.
              </p>
            </div>
            <CodeSample
              name="시작하기"
              code={
                '// pnpm workspace에서 사용\npnpm add @jhworks/pattern@workspace:*\n\n// 앱의 전역 스타일에서 한 번 불러오세요\nimport "@jhworks/pattern/tokens.css";\nimport "@jhworks/pattern/components.css";\n\nimport { Button, Badge } from "@jhworks/pattern/react";'
              }
            />
          </section>
          <section id="principles">
            <p className="eyebrow">PRINCIPLES</p>
            <h2>일을 마치는 데 집중합니다.</h2>
            <div className="principle-grid">
              <article>
                <span>01</span>
                <h3>다음 행동을 명확하게</h3>
                <p>
                  빈 화면은 이유와 다음 행동을 함께 안내합니다. 사용할 수 없는 AI 입력창보다 지금
                  가능한 경비 작성을 먼저 제안합니다.
                </p>
              </article>
              <article>
                <span>02</span>
                <h3>필요할 때, 필요한 만큼</h3>
                <p>
                  기본 화면은 짧게 유지합니다. 필수 안내는 보이게, 보충 설명은 도움말과 펼침
                  영역으로 제공합니다.
                </p>
              </article>
              <article>
                <span>03</span>
                <h3>변경은 예상 가능하게</h3>
                <p>
                  저장과 제출을 구분하고, 실행할 문서·금액을 먼저 보여 줍니다. 취소·오류·재시도
                  경로를 함께 설계합니다.
                </p>
              </article>
            </div>
            <p className="pattern-sources">
              참고한 공식 원칙:{' '}
              <a href="https://linear.app/now/behind-the-latest-design-refresh">
                Linear의 시각적 우선순위
              </a>{' '}
              · <a href="https://atlassian.design/foundations/content">Atlassian의 콘텐츠</a> ·{' '}
              <a href="https://carbondesignsystem.com/components/tooltip/usage/">Carbon의 도움말</a>{' '}
              · <a href="https://tailwindcss.com/docs/theme">Tailwind의 토큰 API</a>
            </p>
          </section>
          <section id="tokens">
            <p className="eyebrow">FOUNDATIONS</p>
            <h2>의미를 가진 디자인 토큰</h2>
            <p>
              값의 원본은 <code>packages/pattern/tokens.json</code>입니다. 생성된 CSS와 이 목록이
              같은 원본을 사용하므로 제품과 문서의 값을 함께 바꿀 수 있습니다.
            </p>
            <p role="status">
              {query
                ? `‘${query}’와 일치하는 토큰 ${foundTokens.length}개 · 컴포넌트 ${foundComponents.length}개`
                : `${tokens.length}개 토큰`}
            </p>
            <div className="pattern-table-wrap">
              <table>
                <caption className="sr-only">JHW 디자인 토큰 이름·값·사용 목적</caption>
                <thead>
                  <tr>
                    <th>토큰</th>
                    <th>값</th>
                    <th>사용 목적</th>
                  </tr>
                </thead>
                <tbody>
                  {foundTokens.map((token) => (
                    <tr key={token.name}>
                      <td>
                        <code>{token.name}</code>
                      </td>
                      <td>
                        {token.group === 'color' && (
                          <span
                            className="token-swatch"
                            aria-hidden="true"
                            style={{ background: `var(${token.name})` }}
                          />
                        )}
                        <code>{token.value}</code>
                      </td>
                      <td>{token.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {foundTokens.length === 0 && (
              <p>일치하는 토큰이 없습니다. 다른 이름이나 사용 목적으로 검색해 보세요.</p>
            )}
            <CodeSample
              name="토큰"
              code={
                '.notice {\n  color: var(--jhw-color-text);\n  background: var(--jhw-color-surface);\n  padding: var(--jhw-space-4);\n  border-radius: var(--jhw-radius-md);\n}'
              }
            />
          </section>
          <section id="components">
            <p className="eyebrow">COMPONENTS</p>
            <h2>직접 조작하며 살펴보세요.</h2>
            {foundComponents.map((item) => (
              <article className="pattern-component" key={item.id}>
                <h3>
                  {item.name} <small>{item.label}</small>
                </h3>
                <p>{item.summary}</p>
                <div className="pattern-preview">
                  {item.id === 'button' ? (
                    <>
                      <Button onClick={() => setClicked(true)}>초안 저장</Button>
                      <Button variant="secondary">취소</Button>
                      <Button variant="danger">반려</Button>
                      <Button disabled aria-busy="true">
                        저장 중…
                      </Button>
                      <span role="status">
                        {clicked ? '예제 버튼을 눌렀습니다. 업무 데이터는 변경되지 않습니다.' : ''}
                      </span>
                    </>
                  ) : item.id === 'badge' ? (
                    <>
                      <Badge>초안</Badge>
                      <Badge tone="info">결재 대기</Badge>
                      <Badge tone="success">승인</Badge>
                      <Badge tone="danger">반려</Badge>
                    </>
                  ) : (
                    <span>
                      초안과 제출은 별도 단계입니다.{' '}
                      <ContextHint label="초안과 제출의 차이">
                        초안 저장은 작성 중인 내용을 보관하고, 제출은 지정 결재자에게 검토를
                        요청합니다.
                      </ContextHint>
                    </span>
                  )}
                </div>
                <CodeSample
                  name={item.name}
                  code={
                    item.id === 'button'
                      ? '<Button onClick={save}>초안 저장</Button>\n<Button variant="secondary">취소</Button>\n<Button disabled aria-busy="true">저장 중…</Button>'
                      : item.id === 'badge'
                        ? '<Badge tone="info">결재 대기</Badge>\n<Badge tone="success">승인</Badge>'
                        : '// 제품 내부의 접근성 패턴 (패키지 export 준비 중)\n<ContextHint label="초안과 제출의 차이">\n  초안 저장과 제출은 별도 단계입니다.\n</ContextHint>'
                  }
                />
              </article>
            ))}
            {foundComponents.length === 0 && <p>일치하는 컴포넌트가 없습니다.</p>}
          </section>
          <section id="workflow">
            <p className="eyebrow">WORKFLOW</p>
            <h2>컴포넌트 사이의 규칙도 패턴입니다.</h2>
            <ol className="workflow-rules">
              <li>
                <strong>작성 → 확인 → 제출</strong>
                <p>
                  ‘저장’으로 즉시 제출하지 않습니다. 문서·금액·현재 버전을 보여 준 뒤 사용자가
                  확인합니다.
                </p>
              </li>
              <li>
                <strong>완료 → 다음 행동</strong>
                <p>
                  초안은 보완과 제출로, 결재 대기는 역할 전환으로, 승인은 결과 확인으로 연결합니다.
                </p>
              </li>
              <li>
                <strong>처음 사용 → 스스로 완료</strong>
                <p>
                  첫 안내는 세 단계 이내로, 닫기와 다시 보기를 제공합니다. 가이드를 따라도 결재나
                  데이터 변경을 자동 실행하지 않습니다.
                </p>
              </li>
            </ol>
          </section>
          <section id="accessibility">
            <p className="eyebrow">QUALITY</p>
            <h2>접근성과 배포 기준</h2>
            <ul>
              <li>버튼에는 행동 이름을, 상태에는 색과 글자를 함께 제공합니다.</li>
              <li>
                키보드 포커스를 표시하고 도움말은 hover·focus·터치에서 접근할 수 있게 합니다. Esc로
                닫을 수 있습니다.
              </li>
              <li>움직임 줄이기 설정을 존중합니다. 실행 중 버튼은 중복 입력을 막습니다.</li>
              <li>
                npm 공개 전에는 사용 API·키보드 동작·패키지 내용·라이선스·이름과 소유권을
                확정합니다.
              </li>
            </ul>
            <p>
              현재 패키지는 <code>private: true</code>이며 외부에 게시되지 않았습니다. 전체 화면의
              토큰 전환은 단계적으로 진행하며 레거시 CSS 별칭을 함께 유지합니다.
            </p>
          </section>
          <footer className="pattern-footer">
            JHW Pattern · Built with the same patterns as JHWorks.
            <Link href="/">업무 화면으로 돌아가기 →</Link>
          </footer>
        </main>
      </div>
    </div>
  );
}
