// Test the static build under its real deployment prefix, without an application API.
import { createServer } from 'node:http';
import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import { dirname, extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../apps/pattern-storybook/storybook-static');
const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.woff2': 'font/woff2', '.woff': 'font/woff', '.ico': 'image/x-icon' };
createServer(async (request, response) => {
  try {
    const path = new URL(request.url, 'http://127.0.0.1').pathname;
    if (path === '/storybook') { response.writeHead(302, { Location: '/storybook/' }).end(); return; }
    if (!path.startsWith('/storybook/')) { response.writeHead(404).end(); return; }
    let target = resolve(root, decodeURIComponent(path.slice('/storybook/'.length)));
    if (target !== root && !target.startsWith(root + sep)) { response.writeHead(404).end(); return; }
    if ((await stat(target)).isDirectory()) target = resolve(target, 'index.html');
    response.writeHead(200, { 'Content-Type': mime[extname(target)] ?? 'application/octet-stream', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' });
    if (request.method === 'HEAD') response.end();
    else createReadStream(target).on('error', () => response.destroy()).pipe(response);
  } catch { response.writeHead(404).end(); }
}).listen(6006, '127.0.0.1', () => console.log('Static Storybook: http://127.0.0.1:6006/storybook/'));
