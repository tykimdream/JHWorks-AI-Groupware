'use client';

import { Button } from '@jhworks/pattern/react';
import { useEffect, useId, useRef, type ReactNode } from 'react';

export function ConfirmationDialog({ open, title, description, confirmLabel, cancelLabel = '취소', busy = false, onCancel, onConfirm, children }: {
  open: boolean; title: string; description: string; confirmLabel: string; cancelLabel?: string;
  busy?: boolean; onCancel: () => void; onConfirm: () => void; children?: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const confirm = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) { element.showModal(); cancel.current?.focus(); }
    else if (!open && element.open) element.close();
  }, [open]);
  return <dialog ref={dialog} className="approval-command-dialog" aria-labelledby={titleId} aria-describedby={descriptionId} aria-busy={busy}
    onCancel={(event) => { event.preventDefault(); if (!busy) onCancel(); }}
    onKeyDown={(event) => {
      if (event.key !== 'Tab' || busy) return;
      if (event.shiftKey && event.target === cancel.current) { event.preventDefault(); confirm.current?.focus(); }
      else if (!event.shiftKey && event.target === confirm.current) { event.preventDefault(); cancel.current?.focus(); }
    }}>
    <h2 id={titleId}>{title}</h2><p id={descriptionId}>{description}</p>
    {children}
    <div className="button-row">
      <Button ref={cancel} variant="secondary" disabled={busy} onClick={onCancel}>{cancelLabel}</Button>
      <Button ref={confirm} disabled={busy} onClick={onConfirm}>{busy ? '처리 중…' : confirmLabel}</Button>
    </div>
  </dialog>;
}
