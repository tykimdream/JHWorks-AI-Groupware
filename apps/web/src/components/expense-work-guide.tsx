'use client';

import { useEffect, useRef, useState } from 'react';
import { apiFetch, getUserErrorMessage } from '@/lib/api';
import type { Approval } from '@/lib/types';

interface Guide {
  version: string;
  source: string;
  fields: { field: string; label: string; description: string; example: string; required: boolean }[];
  stages: { status: string; title: string; meaning: string; nextStep: string }[];
  questions: { id: string; question: string; answer: string }[];
}
interface SavedChecks { version: number; missingFields: string[] }

export function ExpenseWorkGuide({ approval, onFocusField }: {
  approval?: Approval;
  onFocusField?: (field: string) => void;
}) {
  const trigger = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  return <>
    <div className="tw:my-4 tw:flex tw:flex-wrap tw:items-center tw:justify-between tw:gap-3">
      <p className="tw:m-0 tw:text-sm tw:text-jhw-muted">처음 정산하나요? 단계와 필요한 정보를 확인하세요.</p>
      <button type="button" ref={trigger} className="secondary-button" aria-haspopup="dialog" onClick={() => setOpen(true)}>경비 업무 도움말</button>
    </div>
    {open && <GuideDialog approval={approval} onFocusField={onFocusField} onClose={() => { setOpen(false); trigger.current?.focus(); }} />}
  </>;
}

function GuideDialog({ approval, onFocusField, onClose }: {
  approval?: Approval;
  onFocusField?: (field: string) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const jump = useRef<string | null>(null);
  const [guide, setGuide] = useState<Guide | null>(null);
  const [checks, setChecks] = useState<SavedChecks | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checksError, setChecksError] = useState<string | null>(null);
  const [question, setQuestion] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const node = dialog.current;
    if (node && !node.open) node.showModal();
    // Removing the dialog closes it. Explicit cleanup would emit a close event
    // during React Strict Mode's effect replay and dismiss a newly opened panel.
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    apiFetch<Guide>('/approvals/expense-guide', { signal: controller.signal })
      .then((value) => { if (!controller.signal.aborted) { setGuide(value); setError(null); } })
      .catch((caught) => { if (!controller.signal.aborted) setError(getUserErrorMessage(caught, '업무 안내를 불러오지 못했습니다. 다시 조회해 주세요.')); });
    if (approval) apiFetch<SavedChecks>(`/approvals/${approval.id}/expense-checks`, { signal: controller.signal })
      .then((value) => { if (!controller.signal.aborted) {
        if (value.version !== approval.version) { setChecksError('저장된 문서가 바뀌었습니다. 화면을 새로고침해 주세요.'); return; }
        setChecks(value); setChecksError(null);
      } }).catch((caught) => { if (!controller.signal.aborted) setChecksError(getUserErrorMessage(caught, '저장된 문서의 경비 필드를 검사하지 못했습니다.')); });
    return () => controller.abort();
  }, [approval, attempt]);
  const stage = guide?.stages.find((item) => item.status === (approval?.status ?? 'DRAFT'));
  const selected = guide?.questions.find((item) => item.id === question);
  return <dialog ref={dialog} aria-labelledby="expense-help-title" onClose={() => {
    const target = jump.current;
    onClose();
    if (target) onFocusField?.(target);
  }} className="tw:fixed tw:inset-y-0 tw:right-0 tw:left-auto tw:m-0 tw:ml-auto tw:h-dvh tw:max-h-dvh tw:w-full tw:max-w-md tw:overflow-y-auto tw:overscroll-contain tw:border-0 tw:bg-jhw-surface tw:p-0 tw:text-jhw-text tw:shadow-xl tw:backdrop:bg-black/25">
    <header className="tw:sticky tw:top-0 tw:z-10 tw:flex tw:items-center tw:justify-between tw:gap-3 tw:border-0 tw:border-b tw:border-solid tw:border-jhw-border tw:bg-jhw-surface tw:p-5">
      <h2 id="expense-help-title" className="tw:m-0 tw:text-xl">경비 업무 도움말</h2>
      <button type="button" autoFocus className="text-button" onClick={() => dialog.current?.close()}>닫기</button>
    </header>
    <div className="tw:space-y-6 tw:p-5 tw:text-sm tw:leading-6">
      <p className="tw:mt-0 tw:text-jhw-muted">서버 업무 계약에 따른 안내입니다. AI 대화나 규정 전체 판정은 아닙니다. 도움말을 열거나 질문을 눌러도 문서는 바뀌지 않습니다.</p>
      {error && <p role="alert" className="error-banner">{error}</p>}
      {!guide && !error && <p role="status">업무 안내를 불러오는 중입니다.</p>}
      {guide && <>
        {stage && <section aria-label="현재 업무 단계" className="tw:rounded-lg tw:bg-jhw-canvas tw:p-4">
          <h3 className="tw:mt-0">{stage.title}{approval ? ` · 저장된 v${approval.version}` : ' · 작성 중'}</h3>
          <p>{stage.meaning}</p><p className="tw:mb-0"><strong>다음 단계</strong><br />{stage.nextStep}</p>
        </section>}
        <section aria-label="자주 묻는 경비 질문">
          <h3>궁금한 것을 선택하세요</h3>
          <div className="tw:grid tw:gap-2">{guide.questions.map((item) => <button type="button" key={item.id} aria-pressed={question === item.id} onClick={() => setQuestion(item.id)} className="tw:cursor-pointer tw:rounded-lg tw:border tw:border-solid tw:border-jhw-border tw:bg-jhw-canvas tw:p-3 tw:text-left tw:text-jhw-text">{item.question}</button>)}</div>
          <div role="status" aria-live="polite" className="tw:my-4 tw:border-0 tw:border-l-2 tw:border-solid tw:border-jhw-primary tw:pl-3">{selected && <><strong>{selected.question}</strong><p>{selected.answer}</p></>}</div>
        </section>
        <section aria-label="경비 필드 검사 안내">
          <h3>어떤 정보가 필요한가요?</h3>
          <p>제출 시 제목·업무 내용과 결재자 조건도 함께 검사합니다.</p>
          {approval ? <>
            <p className="tw:text-jhw-muted">저장된 v{approval.version}의 경비 필드만 검사합니다. 화면에서 아직 저장하지 않은 수정은 포함하지 않습니다.</p>
            {checksError ? <p role="alert">{checksError}</p> : !checks ? <p role="status">저장된 경비 필드를 검사하는 중입니다.</p> : <p>{checks.missingFields.length ? '보완이 필요한 경비 필드가 있습니다.' : '필수 경비 필드가 입력됐습니다. 제출 가능·규정 준수·실제 지출이 확인됐다는 뜻은 아닙니다.'}</p>}
          </> : <p className="tw:text-jhw-muted">새 문서의 입력값은 검사하거나 전송하지 않습니다. 아래는 일반적인 작성 기준입니다.</p>}
          <dl className="tw:space-y-4">{guide.fields.map((field) => <div key={field.field} className="tw:border-0 tw:border-l-2 tw:border-solid tw:border-jhw-border tw:pl-3">
            <dt className="tw:font-semibold">{field.label} · {field.required ? '필수' : '선택'}{checks?.missingFields.includes(field.field) ? ' · 보완 필요' : ''}</dt>
            <dd className="tw:m-0"><p className="tw:my-1">{field.description}</p><p className="tw:my-1 tw:text-jhw-muted">합성 예시: {field.example}</p>
              {onFocusField && <button type="button" className="text-button" onClick={() => { jump.current = field.field; dialog.current?.close(); }}>{field.label} 입력으로 이동</button>}
            </dd>
          </div>)}</dl>
        </section>
        <details><summary className="tw:cursor-pointer">다른 단계도 알아보기</summary>{guide.stages.filter((item) => item.status !== stage?.status).map((item) => <section key={item.status}><h4>{item.title}</h4><p>{item.meaning}</p><p>{item.nextStep}</p></section>)}</details>
        <p className="tw:text-xs tw:text-jhw-muted">출처: {guide.source} · {guide.version}</p>
      </>}
      {(error || checksError) && <button type="button" className="secondary-button" onClick={() => { setChecks(null); setChecksError(null); setError(null); setAttempt((value) => value + 1); }}>안내 다시 조회</button>}
    </div>
  </dialog>;
}
