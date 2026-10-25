export { tokens } from './catalog.js';
const variants = new Set(['primary', 'secondary', 'danger', 'ghost']);
export function buttonClass(variant = 'primary') {
  if (!variants.has(variant)) throw new TypeError('Unknown JHW button variant');
  return `jhw-button jhw-button--${variant}`;
}
