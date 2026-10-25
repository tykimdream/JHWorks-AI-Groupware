import { createElement } from 'react';
import { buttonClass } from './index.js';
export function Button({ variant = 'primary', className = '', type = 'button', ...props }) {
  return createElement('button', {
    ...props,
    type,
    className: `${buttonClass(variant)} ${className}`.trim(),
  });
}
export function Badge({ tone = 'neutral', className = '', ...props }) {
  return createElement('span', {
    ...props,
    className: `jhw-badge jhw-badge--${tone} ${className}`.trim(),
  });
}
