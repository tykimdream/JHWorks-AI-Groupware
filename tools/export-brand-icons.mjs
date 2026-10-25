// Render directly from icon.svg. Requires the project's Playwright Chromium.
import { chromium } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';

const app = new URL('../apps/web/src/app/', import.meta.url);
const svg = await readFile(new URL('icon.svg', app), 'utf8');
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  const render = async (size, square = false) => {
    await page.setViewportSize({ width: size, height: size });
    // iOS applies its own corner mask; the Apple image has an opaque square base.
    const artwork = square ? svg.replace(' rx="10"', '') : svg;
    await page.setContent(`<style>html,body{margin:0}svg{display:block;width:100vw;height:100vh}</style>${artwork}`);
    return page.screenshot({ omitBackground: true });
  };
  const sizes = [16, 32, 48];
  const images = [];
  for (const size of sizes) images.push(await render(size));
  const directory = Buffer.alloc(6 + sizes.length * 16);
  directory.writeUInt16LE(1, 2); // ICO
  directory.writeUInt16LE(sizes.length, 4);
  let offset = directory.length;
  for (const [index, size] of sizes.entries()) {
    const entry = 6 + index * 16;
    directory[entry] = size;
    directory[entry + 1] = size;
    directory.writeUInt16LE(1, entry + 4);
    directory.writeUInt16LE(32, entry + 6);
    directory.writeUInt32LE(images[index].length, entry + 8);
    directory.writeUInt32LE(offset, entry + 12);
    offset += images[index].length;
  }
  await writeFile(new URL('favicon.ico', app), Buffer.concat([directory, ...images]));
  await writeFile(new URL('apple-icon.png', app), await render(180, true));
  console.log('Exported favicon.ico (16/32/48) and apple-icon.png (180).');
} finally {
  await browser.close();
}
