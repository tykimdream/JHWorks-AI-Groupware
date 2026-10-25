'use client';

import { createContext, createElement as h, useContext, useEffect, useId, useRef } from 'react';
import { buttonClass } from './index.js';

const FieldContext = createContext(null);
export function Field({ id: suppliedId, label, description, error, disabled = false, required = false, children, className = '' }) {
  const generated = useId();
  const id = suppliedId ?? `jhw-field-${generated}`;
  const descriptionId = description ? `${id}-description` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  return h('div', { className: `jhw-field ${className}`.trim() },
    h('label', { className: 'jhw-field__label', htmlFor: id }, label, required ? h('span', { 'aria-hidden': true }, ' *') : null),
    h(FieldContext.Provider, { value: { id, descriptionId, errorId, disabled, required } }, children),
    description ? h('p', { id: descriptionId, className: 'jhw-field__description' }, description) : null,
    error ? h('p', { id: errorId, className: 'jhw-field__error' }, error) : null);
}

function useControl(props) {
  const field = useContext(FieldContext);
  const descriptions = [props['aria-describedby'], field?.descriptionId, field?.errorId].filter(Boolean).join(' ') || undefined;
  return { ...props, id: field?.id ?? props.id, disabled: field?.disabled || props.disabled,
    required: field?.required || props.required, 'aria-invalid': field?.errorId ? true : props['aria-invalid'],
    'aria-describedby': descriptions, className: `jhw-input ${props.className ?? ''}`.trim() };
}
export function Input(props) { return h('input', useControl(props)); }
export function Select(props) { return h('select', useControl(props)); }
export function Textarea(props) { return h('textarea', useControl(props)); }

export function Alert({ tone = 'info', title, children, className = '', role, ...props }) {
  return h('div', { ...props, role: role ?? (tone === 'danger' ? 'alert' : 'status'), className: `jhw-alert jhw-alert--${tone} ${className}`.trim() },
    title ? h('strong', null, title) : null, children);
}
export function EmptyState({ title, description, children, className = '', ...props }) {
  return h('section', { ...props, className: `jhw-empty-state ${className}`.trim() }, h('strong', null, title),
    description ? h('p', null, description) : null, children);
}

// Confirmation body is read-only context. Use a dedicated form dialog for interactive bodies.
export function ConfirmationDialog({ open, title, description, confirmLabel, cancelLabel = '취소', busy = false, onCancel, onConfirm, children }) {
  const dialog = useRef(null);
  const cancel = useRef(null);
  const confirm = useRef(null);
  const titleId = useId();
  const descriptionId = useId();
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) { element.showModal(); cancel.current?.focus(); }
    else if (!open && element.open) element.close();
  }, [open]);
  return h('dialog', { ref: dialog, className: 'jhw-confirmation-dialog', 'aria-labelledby': titleId, 'aria-describedby': descriptionId, 'aria-busy': busy,
    onCancel: (event) => { event.preventDefault(); if (!busy) onCancel(); },
    onKeyDown: (event) => {
      if (event.key !== 'Tab' || busy) return;
      if (event.shiftKey && event.target === cancel.current) { event.preventDefault(); confirm.current?.focus(); }
      else if (!event.shiftKey && event.target === confirm.current) { event.preventDefault(); cancel.current?.focus(); }
    } }, h('h2', { id: titleId }, title), h('p', { id: descriptionId }, description), children,
    h('div', { className: 'jhw-confirmation-dialog__actions' },
      h('button', { ref: cancel, className: buttonClass('secondary'), type: 'button', disabled: busy, onClick: onCancel }, cancelLabel),
      h('button', { ref: confirm, className: buttonClass('primary'), type: 'button', disabled: busy, onClick: onConfirm }, busy ? '처리 중…' : confirmLabel)));
}
