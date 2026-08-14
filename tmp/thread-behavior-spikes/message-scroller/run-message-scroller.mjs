import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join } from 'node:path';

const root = new URL('./src/spikes/', import.meta.url);
const server = createServer(async (req, res) => {
  const path = req.url === '/' ? 'message-scroller-scenario.html' : req.url.slice(1);
  try { const data = await readFile(new URL(path, root)); res.writeHead(200, {'content-type': extname(path)==='.html'?'text/html':'text/plain'}); res.end(data); }
  catch { res.writeHead(404); res.end('not found'); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const port = server.address().port;
const browser = await chromium.launch({headless: true});
const page = await browser.newPage({viewport: {width: 900, height: 760}, hasTouch: true});
await page.goto(`http://127.0.0.1:${port}/`);
const cancelOutcomes = await page.evaluate(() => {
  const s = window.__messageScrollerSpike, before = s.state.cancellations.length;
  s.scroller.begin(); s.viewport.dispatchEvent(new WheelEvent('wheel')); s.scroller.begin(); s.viewport.dispatchEvent(new Event('touchstart')); s.scroller.begin(); s.viewport.dispatchEvent(new PointerEvent('pointerdown')); s.scroller.begin(); s.viewport.dispatchEvent(new Event('selectstart')); s.scroller.begin(); s.viewport.dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowDown'}));
  return {before, after:s.state.cancellations.length, reasons:s.state.cancellations.slice(-5).map(x=>x.reason)};
});
const turns = [];
for (let i=1; i<=10; i++) {
  const text = i % 2 ? 'duplicate initiation' : `real textarea turn ${i}`;
  await page.locator('#input').fill(text);
  await page.locator('#send').click();
  await page.waitForFunction(n => window.__messageScrollerSpike.state.turns.length === n && window.__messageScrollerSpike.state.turns[n-1].closed, i);
  turns.push(await page.evaluate(n => window.__messageScrollerSpike.state.placements[n-1], i-1));
}
const result = await page.evaluate(() => {
  const s=window.__messageScrollerSpike, v=s.viewport;
  const ids=[...document.querySelectorAll('[data-message-id]')].map(x=>x.dataset.messageId);
  const humanIds=s.state.values.map(x=>x.id);
  const assistantIds=s.state.turns.map(x=>x.assistantId);
  const boundary=s.boundary();
  const hydrated=s.hydrate();
  return {actualScrollHeight:v.scrollHeight, clientHeight:v.clientHeight, scrollTop:v.scrollTop, humanIds, assistantIds, values:s.state.values, placements:s.state.placements, duplicateRenderedCount:document.querySelectorAll('[data-message-id="human-duplicate"]').length, renderedMessageCount:ids.length, cancellationOutcomes:s.state.cancellations, boundary, hydrated, headerClipped:s.headerClipped(), controls:{send:!!document.querySelector('#send'), textarea:!!document.querySelector('#input')}};
});
console.log(JSON.stringify({scenario:'MessageScroller adapted source-pattern prototype', turns, ...result}, null, 2));
await browser.close(); server.close();
