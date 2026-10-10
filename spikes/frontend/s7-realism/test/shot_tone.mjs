// compare tone mappers: node shot_tone.mjs "agx,aces,neutral" "corner,east,sun" "1050:1730,1110:1830" tag
import { chromium } from 'playwright';
const out = '/tmp/spk/shots9';
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
const logs = []; page.on('console', (m) => { if (m.type() === 'error') logs.push(m.text()); }); page.on('pageerror', (e) => logs.push(e.message));
await page.goto('http://127.0.0.1:8777/index.html');
await page.waitForFunction(() => !document.getElementById('goLook').disabled, null, { timeout: 240000 });
await page.click('#goLook'); await page.waitForTimeout(2500);
const tones = process.argv[2].split(','), views = process.argv[3].split(','), times = process.argv[4].split(',').map((x) => x.split(':'));
const tag = process.argv[5] || 't';
for (const tone of tones) {
  await page.evaluate((v) => document.querySelector(`#panel .row[data-key=tone] button[data-v=${v}]`).click(), tone);
  await page.waitForTimeout(2500);
  for (const [m, tt] of times) {
    await page.evaluate((m) => { const s = document.getElementById('time'); s.value = m; s.dispatchEvent(new Event('input', { bubbles: true })); }, +m);
    await page.waitForTimeout(2000);
    for (const v of views) {
      await page.click(`#bar [data-view=${v}]`); await page.waitForTimeout(2200);
      await page.screenshot({ path: `${out}/${tag}_${tone}_${v}_${tt}.png` });
    }
  }
}
console.log('errors:', logs.join(' / ') || 'none');
await browser.close();
