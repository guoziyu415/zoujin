// headless check of the S7 page: errors, load marks, screenshots per view and lighting mode
import { chromium } from 'playwright';
const url = process.argv[2] || 'http://127.0.0.1:8777/index.html';
const outDir = process.argv[3] || '/tmp/spk/shots';
const views = (process.argv[4] || 'entry,sun,talk').split(',');
const modes = (process.argv[5] || 'indirect').split(',');
const extra = (process.argv[6] || '').split(';').filter(Boolean).map((kv) => kv.split('='));
const tag = process.argv[7] || '';
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
const logs = [];
page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`));
page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`));
await page.goto(url);
await page.waitForFunction(() => !document.getElementById('goLook').disabled || /失败/.test(document.getElementById('loadmsg').textContent), null, { timeout: 240000 });
console.log('loadmsg:', await page.textContent('#loadmsg'));
await page.click('#goLook');
for (const mode of modes) {
  await page.evaluate(async (m) => { document.querySelector(`#panel .row[data-key=light] button[data-v=${m}]`).click(); }, mode);
  for (const [k, v] of extra) await page.evaluate(([k, v]) => document.querySelector(`#panel .row[data-key=${k}] button[data-v="${v}"]`).click(), [k, v]);
  await page.waitForTimeout(4000);
  for (const v of views) {
    await page.click(`#bar [data-view=${v}]`);
    await page.waitForTimeout(2500);
    await page.screenshot({ path: `${outDir}/${mode}_${v}${tag}.png` });
  }
}
console.log(logs.filter((l) => !l.includes('GPU stall')).slice(0, 40).join('\n'));
await browser.close();
