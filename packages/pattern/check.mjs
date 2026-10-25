import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { Button, Badge } from './react.js';
import { tokens, buttonClass } from './index.js';

// Package boundary: no Next.js runtime or implicit form submission.
const handler = () => {};
const reference = { current: null };
const button = Button({
  children: '저장',
  onClick: handler,
  ref: reference,
  disabled: true,
  'aria-busy': true,
});
assert.equal(button.type, 'button');
assert.equal(button.props.type, 'button');
assert.equal(button.props.onClick, handler);
assert.equal(button.props.ref, reference);
assert.equal(button.props.disabled, true);
assert.equal(button.props['aria-busy'], true);
assert.equal(Button({ type: 'submit' }).props.type, 'submit');
assert.match(Badge({ tone: 'success', children: '승인' }).props.className, /jhw-badge--success/);
assert.throws(() => buttonClass('unsupported'), TypeError);
assert.equal(new Set(tokens.map((t) => t.name)).size, tokens.length);
assert.ok(tokens.every((t) => t.name.startsWith('--jhw-')));
const manifest = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8'));
assert.equal(manifest.private, true);
for (const file of manifest.files)
  assert.ok(existsSync(new URL(file, import.meta.url)), `Missing package file: ${file}`);
console.log('JHW Pattern package contract passed');
