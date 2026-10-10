// Headless check of the A-0 page: loads, renders each view, speaks a line. Screenshots into <out>.
// node test_page.mjs <page_dir> <out_dir> [w h]
import { chromium } from '/tmp/spk/node_modules/playwright/index.mjs';
import http from 'http';
import fs from 'fs';
import path from 'path';

const [, , ROOT, OUT, W = '393', H = '852'] = process.argv;
fs.mkdirSync(OUT, { recursive: true });
const THREE_DIR = '/tmp/spk/node_modules/three';
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.jpg': 'image/jpeg', '.png': 'image/png', '.wasm': 'application/wasm' };
const srv = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'content-type': TYPES[path.extname(p)] || 'application/octet-stream' }); fs.createReadStream(p).pipe(res);
}).listen(8765);
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--autoplay-policy=no-user-gesture-required'] });
const page = await browser.newPage({ viewport: { width: +W, height: +H }, deviceScaleFactor: 1 });
page.setDefaultTimeout(180000);
const logs = [];
page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`));
page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`));
await page.route('https://cdn.jsdelivr.net/npm/three@0.186.1/**', (route) => {
  const rel = route.request().url().split('three@0.186.1/')[1];
  const f = path.join(THREE_DIR, rel);
  if (!fs.existsSync(f)) return route.fulfill({ status: 404 });
  route.fulfill({ status: 200, body: fs.readFileSync(f), contentType: TYPES[path.extname(f)] || 'application/octet-stream' });
});
const t0 = Date.now();
await page.goto('http://localhost:8765/index.html?debug');
await page.waitForFunction(() => !document.getElementById('goLook').disabled || /失败/.test(document.getElementById('loadmsg').textContent), null, { timeout: 240000 });
console.log('loaded in', (Date.now() - t0) / 1000, 's:', await page.textContent('#loadmsg'));
await page.screenshot({ path: path.join(OUT, '0_cover.png') });
const fps = async () => page.evaluate(() => new Promise((r) => { let n = 0; const t = performance.now(); const f = () => { if (++n < 4) requestAnimationFrame(f); else r(((performance.now() - t) / 3).toFixed(0) + ' ms/frame'); }; requestAnimationFrame(f); }));
const shot = async (name, wait = 4000) => { console.log('frame time', await fps()); await page.waitForTimeout(wait); await page.screenshot({ path: path.join(OUT, name + '.png') }); console.log(name, JSON.stringify(await page.textContent('#hud'))); };
try { if (!(await page.isDisabled('#goLook'))) {
  await page.click('#goLook');
  await shot('1_talk', 8000);
  console.log('melos meshes', JSON.stringify(await page.evaluate(() => { const o = []; window.__a0.melos.root.traverse((m) => { if (m.isMesh) o.push([m.name, m.castShadow, Object.keys(m.morphTargetDictionary || {}).length]); }); return o; })));
  await page.click('[data-say="m"]');
  await page.waitForTimeout(900);
  await page.screenshot({ path: path.join(OUT, '1b_talk_speaking.png') });
  for (const [t, name] of [[720, 'noon'], [1130, '1850']]) { await page.evaluate((m) => window.__a0.setTime(m, true), t); await shot('1c_talk_' + name, 5000); }
  await page.evaluate(() => window.__a0.setTime(1050, true));
  for (const v of ['face', 'pair', 'explore', 'backlit']) { await page.click(`[data-view="${v}"]`); await shot('2_' + v, 6000); }
  await page.click('[data-view="face"]'); await page.waitForTimeout(3000);
  for (let k = 0; k < 4; k++) { if (k === 0) await page.click('[data-say="l"]'); await page.waitForTimeout(450); await page.screenshot({ path: path.join(OUT, `3_face_say_${k}.png`) }); }
  console.log('mouth', JSON.stringify(await page.evaluate(() => window.__a0.voiceCur && window.__a0.voiceCur())));
  await page.click('#expr'); await page.waitForTimeout(1500); await page.screenshot({ path: path.join(OUT, '4_face_smile.png') });
} } catch (e) { console.log('FAILED', e.message.split('\n')[0]); }
fs.writeFileSync(path.join(OUT, 'console.txt'), logs.join('\n'));
console.log(logs.filter((l) => /error|warn/i.test(l)).slice(0, 30).join('\n'));
await browser.close(); srv.close();
