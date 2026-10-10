import { chromium } from 'playwright';
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
const logs = []; page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') logs.push(m.text()); }); page.on('pageerror', (e) => logs.push(e.message));
await page.goto('http://127.0.0.1:8777/index.html');
await page.waitForFunction(() => !document.getElementById('goLook').disabled, null, { timeout: 240000 });
console.log(await page.textContent('#loadmsg'));
await page.click('#goBench');
let lastMsg = '';
const t0 = Date.now();
while (Date.now() - t0 < 900000) {
  await page.waitForTimeout(3000);
  const done = await page.evaluate(() => !document.getElementById('results').classList.contains('hidden'));
  const m = await page.textContent('#benchMsg');
  if (m !== lastMsg) { console.log(((Date.now() - t0) / 1000).toFixed(0) + 's', m); lastMsg = m; }
  if (done) break;
}
await page.screenshot({ path: '/tmp/spk/shots8/bench_results.png', fullPage: true });
console.log(await page.textContent('#resState'));
console.log(await page.evaluate(() => [...document.querySelectorAll('#resBody tr')].map((tr) => [...tr.children].map((td) => td.textContent).join(' | ')).join('\n')));
// grab full JSON through the copy button fallback
await page.evaluate(() => { navigator.clipboard.writeText = undefined; });
await page.click('#copyRes').catch(() => {});
await page.waitForTimeout(500);
const dump = await page.evaluate(() => document.getElementById('dump')?.value || '');
import('fs').then((fs) => fs.writeFileSync('/tmp/spk/bench_dump.json', dump));
await page.waitForTimeout(300);
console.log(logs.slice(0, 20).join('\n') || 'no errors');
await browser.close();
