// arbitrary cameras (local coords) at given times, using the test-only hook: node shot_cams.mjs '[["top",[-3,2,90],[-3,2.2,0],70]]' "1050:1730" tag
import { chromium } from 'playwright';
const out = '/tmp/spk/shots9';
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
const logs = []; page.on('console', (m) => { if (m.type() === 'error') logs.push(m.text()); }); page.on('pageerror', (e) => logs.push(e.message));
await page.goto('http://127.0.0.1:8777/index.html');
await page.waitForFunction(() => !document.getElementById('goLook').disabled, null, { timeout: 240000 });
await page.click('#goLook'); await page.waitForTimeout(2500);
const cams = JSON.parse(process.argv[2]);
const times = (process.argv[3] || '1050:1730').split(',').map((x) => x.split(':'));
const tag = process.argv[4] || 'c';
for (const [m, tt] of times) {
  await page.evaluate((m) => { const s = document.getElementById('time'); s.value = m; s.dispatchEvent(new Event('input', { bubbles: true })); }, +m);
  await page.waitForTimeout(2000);
  for (const [name, p, t, fov] of cams) {
    await page.evaluate(([p, t, fov]) => window.__s7.look(p, t, fov), [p, t, fov]); await page.waitForTimeout(2200);
    await page.screenshot({ path: `${out}/${tag}_${name}_${tt}.png` });
  }
}
console.log('errors:', logs.join(' / ') || 'none');
await browser.close();
