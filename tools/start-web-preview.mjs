// Start the built standalone app with its static assets, without a second build.
import { cp, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const root = resolve(import.meta.dirname, '..');
const standalone = resolve(root, 'apps/web/.next/standalone/apps/web');
await mkdir(resolve(standalone, '.next'), { recursive: true });
await cp(resolve(root, 'apps/web/.next/static'), resolve(standalone, '.next/static'), { recursive: true });
await cp(resolve(root, 'apps/web/public'), resolve(standalone, 'public'), { recursive: true });
process.env.HOSTNAME = '127.0.0.1';
process.env.PORT ??= '3100';
await import(pathToFileURL(resolve(standalone, 'server.js')).href);
