// sunset button + noon / night checks in the time mode
import { chromium } from 'playwright';
const out = '/tmp/spk/shots8';
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
const logs = []; page.on('console', (m) => { if (m.type() === 'error') logs.push(m.text()); }); page.on('pageerror', (e) => logs.push(e.message));
await page.goto('http://127.0.0.1:8777/index.html');
await page.waitForFunction(() => !document.getElementById('goLook').disabled, null, { timeout: 240000 });
await page.click('#goLook');
const mode = document => 0;
await page.evaluate(() => document.querySelector('#panel .row[data-key=light] button[data-v=ao]').click());
await page.waitForTimeout(5000);
for (const [m, tag] of (process.argv[2] || '1110:dusk1830,1144:dusk1904,1150:dusk1910,720:noon,450:morning,1230:night').split(',').map((x) => x.split(':')).map(([a, b]) => [+a, b])) {
  await page.evaluate((m) => { const s = document.getElementById('time'); s.value = m; s.dispatchEvent(new Event('input', { bubbles: true })); }, m);
  await page.waitForTimeout(3500);
  await page.click(`#bar [data-view=${process.argv[3] || 'entry'}]`); await page.waitForTimeout(2000);
  await page.screenshot({ path: `${out}/time_${tag}.png` });
  console.log(tag, await page.textContent('#timeNote'));
}
console.log('errors:', logs.join(' / ') || 'none');
await browser.close();
