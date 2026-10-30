'use client';

import Link from 'next/link';
import { useEffect, useId, useRef, useState, useSyncExternalStore } from 'react';
import { buttonClass } from '@jhworks/pattern';
import { Button } from '@jhworks/pattern/react';

const key = 'jhworks.guide.v1';
const changed = 'jhworks-guide-changed';
let fallbackSeen = false;
function seen() {
  try {
    return localStorage.getItem(key) === 'seen' || fallbackSeen;
  } catch {
    return fallbackSeen;
  }
}
function subscribe(callback: () => void) {
  window.addEventListener(changed, callback);
  window.addEventListener('storage', callback);
  return () => {
    window.removeEventListener(changed, callback);
    window.removeEventListener('storage', callback);
  };
}
const steps = [
  {
    title: '경비를 초안으로 저장해요',
    text: '지출일·사용처·금액·업무 목적을 입력하세요. 아직 빠진 정보가 있어도 초안으로 저장할 수 있어요.',
    target: '작성',
  },
  {
    title: '내용을 확인하고 제출해요',
    text: '저장한 문서에서 누락 정보와 중복 후보를 확인하세요. 제출 전 문서와 금액을 한 번 더 보여 드려요.',
    target: '확인·제출',
  },
  {
    title: '결재자가 되어 승인해요',
    text: '화면 메뉴의 ‘결재자로 체험하기’에서 역할을 바꾸세요. 내게 배정된 문서에서 승인한 뒤 작성자로 돌아와 결과를 확인할 수 있어요.',
    target: '승인',
  },
];

export function WelcomeGuide() {
  const wasSeen = useSyncExternalStore(subscribe, seen, () => true);
  const [manual, setManual] = useState(false);
  const [step, setStep] = useState(0);
  const trigger = useRef<HTMLButtonElement>(null);
  const dismiss = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLElement>(null);
  const titleId = useId();
  const panelId = useId();
  const open = !wasSeen || manual;
  function close() {
    const restore = panel.current?.contains(document.activeElement);
    fallbackSeen = true;
    try {
      localStorage.setItem(key, 'seen');
    } catch {
      /* Memory preference still works. */
    }
    window.dispatchEvent(new Event(changed));
    setManual(false);
    if (restore) trigger.current?.focus();
  }
  useEffect(() => {
    if (manual) dismiss.current?.focus();
  }, [manual]);
  return (
    <div className="welcome-guide">
      <Button
        ref={trigger}
        variant="secondary"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => {
          if (open) close();
          else {
            setStep(0);
            setManual(true);
          }
        }}
      >
        사용 가이드
      </Button>
      {open && (
        <aside
          ref={panel}
          id={panelId}
          className="guide-card"
          role="dialog"
          aria-modal="false"
          aria-labelledby={titleId}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.stopPropagation();
              close();
            }
          }}
        >
          <button
            ref={dismiss}
            type="button"
            className="guide-dismiss"
            aria-label="사용 가이드 닫기"
            onClick={close}
          >
            ×
          </button>
          <p className="eyebrow">처음 오셨나요? · {step + 1} / 3</p>
          <ol className="guide-progress" aria-label="체험 순서">
            {steps.map((item, index) => (
              <li key={item.target} aria-current={step === index ? 'step' : undefined}>
                {item.target}
              </li>
            ))}
          </ol>
          <h2 id={titleId} aria-live="polite">
            {steps[step].title}
          </h2>
          <p>{steps[step].text}</p>
          <div className="guide-actions">
            <Button variant="ghost" onClick={close}>
              나중에 볼게요
            </Button>
            {step < 2 ? (
              <Button onClick={() => setStep((value) => value + 1)}>다음</Button>
            ) : (
              <Link className={buttonClass()} href="/approvals/new?type=EXPENSE" onClick={close}>
                경비 정산 시작
              </Link>
            )}
          </div>
          <small>‘사용 가이드’에서 언제든 다시 볼 수 있어요.</small>
        </aside>
      )}
    </div>
  );
}
