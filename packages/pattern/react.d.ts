import type { ComponentPropsWithRef, HTMLAttributes, ReactElement } from 'react';
import type { ButtonVariant } from './index.js';
export function Button(
  props: ComponentPropsWithRef<'button'> & { variant?: ButtonVariant },
): ReactElement;
export function Badge(
  props: HTMLAttributes<HTMLSpanElement> & {
    tone?: 'neutral' | 'info' | 'success' | 'danger' | 'warning';
  },
): ReactElement;
