import { readFileSync, writeFileSync } from 'node:fs';
const { tokens, aliases } = JSON.parse(
  readFileSync(new URL('./tokens.json', import.meta.url), 'utf8'),
);
const css =
  '/* Generated from tokens.json. Run pnpm --filter @jhworks/pattern build. */\n:root {\n' +
  tokens.map((t) => `  ${t.name}: ${t.value};`).join('\n') +
  '\n}\n';
const legacy =
  '/* Optional JHWorks compatibility aliases. */\n:root {\n' +
  Object.entries(aliases)
    .map(([key, value]) => `  ${key}: var(${value});`)
    .join('\n') +
  '\n}\n';
const catalog =
  '// Generated from tokens.json.\nexport const tokens = ' +
  JSON.stringify(tokens, null, 2) +
  ';\n';
for (const [name, content] of [
  ['tokens.css', css],
  ['legacy.css', legacy],
  ['catalog.js', catalog],
]) {
  const path = new URL(name, import.meta.url);
  if (process.argv.includes('--check')) {
    if (readFileSync(path, 'utf8') !== content) throw new Error(`${name} differs from tokens.json`);
  } else writeFileSync(path, content);
}

// WCAG 2.2, 1.4.3: normal text pairs must meet 4.5:1 (not a full accessibility audit).
function luminance(hex) {
  const values = hex
    .slice(1)
    .match(/../g)
    .map((v) => parseInt(v, 16) / 255)
    .map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
}
const color = Object.fromEntries(
  tokens
    .filter((t) => t.group === 'color')
    .map((t) => [t.name.slice('--jhw-color-'.length), t.value]),
);
for (const [foreground, background] of [
  ['text', 'surface'],
  ['text-muted', 'canvas'],
  ['surface', 'primary'],
  ['info', 'info-subtle'],
  ['success', 'success-subtle'],
  ['danger', 'danger-subtle'],
  ['warning', 'warning-subtle'],
]) {
  const a = luminance(color[foreground]);
  const b = luminance(color[background]);
  const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  if (ratio < 4.5) throw new Error(`${foreground}/${background} contrast ${ratio} is below 4.5:1`);
}
