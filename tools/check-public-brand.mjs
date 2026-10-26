// Read-only release smoke: no cookies, demo admission, business writes or model calls.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';

const base = new URL(process.argv[2] ?? 'https://groupware.pikan.dev/');
assert(base.protocol === 'https:' && !base.username && !base.password && base.pathname === '/' && !base.search && !base.hash);
assert(base.hostname === 'groupware.pikan.dev' || (base.hostname.startsWith('favicon---jhworks-demo-') && base.hostname.endsWith('.run.app')));
const get = async (path, headers = {}) => {
  const result = await fetch(new URL(path, base), { headers, signal: AbortSignal.timeout(30000) });
  assert.equal(result.status, 200, `${path}: HTTP ${result.status}`);
  return result;
};
const html = await (await get('/login', { 'User-Agent': 'Twitterbot/1.0' })).text();
assert(html.includes('property="og:title"') && html.includes('property="og:description"'));
assert(html.includes('rel="canonical" href="https://groupware.pikan.dev/login"'));
const links = [...html.matchAll(/<link\b[^>]*\brel="(?:icon|apple-touch-icon)"[^>]*>/g)].map(([tag]) => tag.match(/href="([^"]+)"/)?.[1]);
const paths = new Set(links.map(href => new URL(href, base).pathname));
for (const expected of ['/favicon.ico', '/icon.svg', '/apple-icon.png']) assert(paths.has(expected));
const files = [];
for (const href of links) {
  const target = new URL(href, base);
  assert.equal(target.origin, base.origin);
  assert(['/favicon.ico', '/icon.svg', '/apple-icon.png'].includes(target.pathname));
  const response = await get(target.pathname + target.search);
  const bytes = Buffer.from(await response.arrayBuffer());
  const source = await readFile(new URL(`../apps/web/src/app${target.pathname}`, import.meta.url));
  assert(bytes.equals(source), `${target.pathname}: deployed icon differs from approved source`);
  files.push({ path: target.pathname, contentType: response.headers.get('content-type'), bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') });
}
const imageUrl = new URL(html.match(/property="og:image" content="([^"]+)"/)?.[1] ?? 'https://invalid.example/');
assert.equal(imageUrl.origin, 'https://groupware.pikan.dev');
assert(imageUrl.pathname.startsWith('/opengraph-image'));
const ogResponse = await get(imageUrl.pathname + imageUrl.search);
assert(ogResponse.headers.get('content-type')?.includes('image/png'));
const og = Buffer.from(await ogResponse.arrayBuffer());
assert.equal(og.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
assert.equal(og.readUInt32BE(16), 1200);
assert.equal(og.readUInt32BE(20), 630);
for (const path of ['/api/v1/health/live', '/api/v1/health/ready']) await get(path);
const report = { checkedAt: new Date().toISOString(), base: base.href, faviconLinks: files, ogSize: [1200, 630], health: 'live/ready 200', businessWrites: 0, modelCalls: 0 };
const output = new URL('../artifacts/brand/', import.meta.url);
await mkdir(output, { recursive: true });
await writeFile(new URL(`public-${base.hostname}.json`, output), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report));
