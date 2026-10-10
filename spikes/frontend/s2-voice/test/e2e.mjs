// End-to-end check of the S2 page against test/fake_serve.py (node + playwright; Chromium with a fake microphone).
// node e2e.mjs http://127.0.0.1:8091/
import { chromium } from 'playwright';
const base = process.argv[2] || 'http://127.0.0.1:8091/';
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', '--autoplay-policy=no-user-gesture-required'] });
const ctx = await browser.newContext({ permissions: ['microphone'] });
const page = await ctx.newPage();
const logs = [];
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') logs.push(`${m.type()}: ${m.text()}`); });
page.on('pageerror', (e) => logs.push(`pageerror: ${e.message}`));
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const vis = (sel) => page.locator(sel).isVisible();
await page.goto(base);
await wait(800);
console.log('login visible', await vis('#login'), 'setup visible', await vis('#setup'));
await page.fill('#code', 'WRONG-CODE'); await page.click('#loginBtn'); await wait(1500);
console.log('wrong code msg:', await page.textContent('#loginMsg'));
await page.fill('#code', 'test-test-test'); await page.click('#loginBtn'); await wait(1500);
console.log('after login: setup visible', await vis('#setup'));
const state = () => page.textContent('#state');
async function talk(holdMs) {
  const b = await page.locator('#talk').boundingBox();
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
  await page.mouse.down(); await wait(holdMs); await page.mouse.up();
}
async function waitRows(n, ms = 15000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { const k = await page.evaluate(() => S.rows.filter((r) => r.kind === 'turn').length); if (k >= n) return true; await wait(200); }
  return false;
}
// S-073: no defaults for 出声 / 网络 / 麦克风; pressing before picking them must not start a turn
await page.selectOption('#item', 't1');
await page.click('#connectBtn');
for (let i = 0; i < 40 && !(await state()).includes('可以说话'); i++) await wait(200);
console.log('state after connect:', await state(), '| button:', await page.textContent('#talk'));
await talk(500); await wait(300);
console.log('press without conditions → no turn:', await page.evaluate(() => S.rows.filter((r) => r.kind === 'turn').length === 0), '|', await state());
await page.selectOption('#route', 'bluetooth'); await page.selectOption('#network', '4g'); await page.selectOption('#mode', 'open'); await wait(500);
console.log('button:', await page.textContent('#talk'), '| hint:', await page.textContent('#hint'));
await page.selectOption('#route', 'speaker'); await wait(100);
console.log('hint after speaker:', JSON.stringify(await page.textContent('#hint')));
// item 1: three voice turns (the third one's player text arrives after turn_complete)
for (let i = 1; i <= 3; i++) { await talk(1200); console.log('turn', i, 'recorded', await waitRows(i), '|', await state()); }
// item 5: whisper sentence, CER (turn 6 overall is a "late" one)
await page.click('#hangBtn'); await page.selectOption('#item', 't5');
console.log('item change clears conditions:', await page.evaluate(() => !condOk()));
await page.selectOption('#route', 'speaker'); await page.selectOption('#network', '4g'); await page.selectOption('#mode', 'open');
await page.click('#connectBtn');
for (let i = 0; i < 40 && !(await state()).includes('可以说话'); i++) await wait(200);
for (let i = 4; i <= 6; i++) { await talk(1000); console.log('t5 turn', i, 'recorded', await waitRows(i), 'say now:', await page.textContent('#say')); }
// item 2: barge-in while the reply plays
await page.selectOption('#item', 't2');
await page.selectOption('#route', 'speaker'); await page.selectOption('#network', '4g'); await page.selectOption('#mode', 'open');
await talk(800);
for (let i = 0; i < 50 && !(await page.evaluate(() => S.playing)); i++) await wait(50);
await wait(300);
console.log('playing before barge-in:', await page.evaluate(() => S.playing));
await talk(900);
console.log('interrupted + barge-in turns recorded', await waitRows(8, 20000));   // the interrupted turn gets its own row (bargeInCount 1)
// barge-in after the server finished but while the phone still plays (S-1b rows 11, 19, 26 were missing or timed out)
await talk(800);
for (let i = 0; i < 100 && !(await page.evaluate(() => S.turn && S.turn.complete && S.playing)); i++) await wait(50);
console.log('complete and still playing before barge-in:', await page.evaluate(() => !!(S.turn && S.turn.complete && S.playing)));
await talk(900);
console.log('late barge-in: interrupted turn recorded at once', await waitRows(9, 1000), '| barge-in turn recorded', await waitRows(10, 20000));
// text turn
await page.fill('#textIn', 'こんにちは'); await page.click('#sendText');
console.log('text turn recorded', await waitRows(11));
await wait(500);
const rows = await page.evaluate(() => S.rows);
for (const r of rows) console.log(JSON.stringify(r));
console.log('summary:', await page.textContent('#summary'));
console.log('env:', (await page.textContent('#envT')).slice(0, 300));
console.log('lines:', (await page.textContent('#lines')).slice(0, 300));
await page.screenshot({ path: 's2.png', fullPage: true });
await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({ path: 's2_phone.png', fullPage: true });
// anonymous WS must be refused
const ctx2 = await browser.newContext(); const p2 = await ctx2.newPage(); await p2.goto(base);
const code = await p2.evaluate(() => new Promise((res) => { const w = new WebSocket(`ws://${location.host}/v1/playthroughs/s1b/live`); w.onclose = (e) => res(e.code); }));
console.log('anonymous ws close code', code);
console.log('console:', logs.length ? logs.join('\n') : 'no errors');
await browser.close();
