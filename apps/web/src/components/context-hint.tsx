'use client';

import { useEffect, useId, useRef, useState } from 'react';

/** Supplemental text only. Required instructions stay visible beside the field. */
function placement(rect: DOMRect) {
  const width = Math.min(240, innerWidth - 32);
  const above = rect.bottom + 150 > innerHeight;
  return {
    left: Math.max(16, Math.min(rect.left, innerWidth - width - 16)),
    top: above ? rect.top - 8 : rect.bottom + 8,
    above,
  };
}

export function ContextHint({ label, children }: { label: string; children: string }) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ left: 16, top: 0, above: false });
  function show() {
    const rect = trigger.current?.getBoundingClientRect();
    if (!rect) return;
    setPosition(placement(rect));
    setOpen(true);
  }
  useEffect(() => {
    if (!open) return;
    const reposition = () => {
      const rect = trigger.current?.getBoundingClientRect();
      if (!rect || rect.bottom < 0 || rect.top > innerHeight) setOpen(false);
      else setPosition(placement(rect));
    };
    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', reposition, true);
    return () => {
      window.removeEventListener('resize', reposition);
      window.removeEventListener('scroll', reposition, true);
    };
  }, [open]);
  return (
    <span className="context-hint" onMouseEnter={show} onMouseLeave={() => setOpen(false)}>
      <button
        ref={trigger}
        type="button"
        aria-label={label}
        aria-describedby={open ? id : undefined}
        onFocus={show}
        onBlur={() => setOpen(false)}
        onClick={show}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            event.stopPropagation();
            setOpen(false);
          }
        }}
      >
        ?
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          data-placement={position.above ? 'above' : 'below'}
          style={{
            left: position.left,
            top: position.top,
            transform: position.above ? 'translateY(-100%)' : undefined,
          }}
        >
          {children}
        </span>
      )}
    </span>
  );
}
