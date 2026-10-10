'use strict';
// Voice test page. Talks to the proxy on the same origin:
// POST /v1/auth/login, GET /v1/me, POST /v1/telemetry, WS /v1/playthroughs/s1b/live.
// This file is served to the phone as is, so it carries no names beyond the character's (see the spike README).
const $ = (id) => document.getElementById(id);
const CHARACTER = 'char.melos';
const STORE = 's2-results-v1';
const WHISPER = {   // the proxy side's fixed lines for item 5 (taken from the earlier desktop test, so the error rates compare)
  phone: [
    'こんばんは。この町、なんだか静かですね。',
    'メロスという男を知っていますか。',
    'セリヌンティウスさんの仕事場は、どちらですか。',
    '王様が人を殺すというのは、本当ですか。',
    '私に何かできることはありますか。',
  ],
  earphone: [
    '王様は、どんな方なんですか。',
    'ディオニス王には、どうすれば会えますか。',
    'フィロストラトスという若い石工を見かけませんでしたか。',
    'シラクスの市は、二年前はどんな町だったんですか。',
    'ありがとうございました。また来ます。',
  ],
};
const whisperGroup = () => (sel('route') === 'speaker' ? 'phone' : 'earphone');
const HINTS = {
  t1: '关掉 Wi-Fi，用 Safari。外放说 10 句，再换 AirPods 说 10 句（上面「出声」要跟着改）。每句说完松手，等メロス回答完再说下一句。',
  t2: 'メロス说话说到一半时按下说话键，10 次。看「按下→静音」是否在 200 毫秒以内。',
  t3: '戴 AirPods。「麦克风」先选「对话中常开」说 5 轮，再选「每轮开关」说 5 轮（换做法要先结束对话再开始）。每轮后点一下音质评价。',
  t4: '把侧面的静音键拨到静音，再说 2 轮，回答完点「听得到 / 听不到」。',
  t5: '安静的房间，用睡前的小音量读上面显示的句子，每句读完松手。先手机麦克风 5 句（出声选外放），再耳机麦克风 5 句（出声选 AirPods 或有线，句子会换成另一组）。',
  t6: '在 LINE 里打开同一个地址，点「开始和メロス说话」，说 1 轮。下面「这台设备」会记下浏览器、麦克风和 Cookie 的结果。',
  t7: '对话中切到别的 App，等 1 分钟再回来。如果出现「タップで音を戻す」就点它，然后再说 1 轮。',
  t8: '打开 Wi-Fi，外放说 5 句，和第 1 项比较。',
};
const RATINGS = { t3: [['good', '音质好'], ['bad', '音质差'], ['stutter', '有卡顿']], t4: [['heard', '听得到'], ['not_heard', '听不到']] };

const S = {
  ctx: null, cap: null, play: null, stream: null, src: null, ws: null,
  seq: 0, turn: null, byId: new Map(), pressed: false, sending: false, ready: false, playing: false,
  connectAt: 0, whisperIdx: 0, hiddenAt: 0, pingTimer: 0,
  rows: [],      // every turn and event, newest last
};
const ENV = {
  browser: browserName(), device: deviceClass(), ua: navigator.userAgent,
  getUserMedia: '未测', cookieSeen: '未测', audioSession: navigator.audioSession ? navigator.audioSession.type : '不支持',
  sampleRate: '-', latency: '-', micOpenMs: '-', connectToReadyMs: '-', micRoute: '-',
};

function browserName() {
  const ua = navigator.userAgent;
  if (/ Line\//i.test(ua)) return 'line';
  if (/FBAN|FBAV|Instagram/i.test(ua)) return 'inapp_other';
  if (/CriOS/.test(ua)) return 'chrome_ios';
  if (/FxiOS/.test(ua)) return 'firefox_ios';
  if (/iPhone|iPad/.test(ua) && /Safari/.test(ua)) return 'safari';
  if (/Chrome/.test(ua)) return 'chrome';
  if (/Safari/.test(ua)) return 'safari_mac';
  return 'other';
}
function deviceClass() { const ua = navigator.userAgent; return /iPhone/.test(ua) ? 'iphone' : /iPad/.test(ua) ? 'ipad' : /Android/.test(ua) ? 'android' : /Mac/.test(ua) ? 'mac' : 'other'; }
const sel = (id) => $(id).value;
// S-073: 出声 / 网络 / 麦克风 have no default; a turn can't start until all three are picked, and the button shows them
const COND = ['route', 'network', 'mode'];
const condOk = () => COND.every((id) => sel(id));
const condText = () => COND.map((id) => $(id).selectedOptions[0]?.textContent || '').join('・');
function talkLabel() { if (!S.pressed) $('talk').textContent = condOk() ? `押して話す（${condText()}）` : '先在上面选「出声 / 网络 / 麦克风」'; checkRoute(); }
function checkRoute() {   // the live mic says headset but 出声 says speaker, or the other way round
  const r = sel('route'), bad = S.extMic != null && r && ((S.extMic === 1) !== (r !== 'speaker'));
  $('hint').textContent = bad ? `麦克风看起来是${S.extMic ? '耳机' : '手机自己的'}，和「出声」选的不一样，请确认` : '';
}
const show = (id, on = true) => $(id).classList.toggle('hidden', !on);
const state = (t) => { $('state').textContent = t; };
const r0 = (v) => (v == null || Number.isNaN(v) ? null : Math.round(v));

// ---------------------------------------------------------------- results
function load() { try { S.rows = JSON.parse(localStorage.getItem(STORE) || '[]'); } catch { S.rows = []; } }
function save() { try { localStorage.setItem(STORE, JSON.stringify(S.rows.slice(-400))); } catch { /* private mode */ } }
function addRow(r) { S.rows.push(r); save(); render(); report(r); }
function report(r) {
  // the proxy keeps only *Ms / *Count / *Pct numbers, turnId / turnSeq and a few short enum keys (s1b_proxy.sanitize_telemetry)
  const e = {};
  for (const [k, v] of Object.entries(r)) {
    if (/(Ms|Count|Pct)$/.test(k) && typeof v === 'number') e[k] = v;
    else if (['item', 'route', 'network', 'browser', 'mode', 'phase', 'device', 'turnId'].includes(k) && typeof v === 'string') e[k] = v.slice(0, 24).toLowerCase();
    else if (k === 'turnSeq') e[k] = v;
  }
  fetch('/v1/telemetry', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ events: [e] }) }).catch(() => {});
}
const pct = (a, p) => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(p * (s.length - 1) + 0.5))]; };
function render() {
  const tb = $('turns'); tb.textContent = '';
  S.rows.slice(-60).reverse().forEach((r) => {
    const tr = document.createElement('tr');
    const other = [];
    if (r.kind === 'turn') {
      if (r.pressToFirstUpMs != null) other.push(`按下→上行 ${r.pressToFirstUpMs}`);
      if (r.firstDownToAudibleMs != null) other.push(`首包→出声 ${r.firstDownToAudibleMs}`);
      if (r.pressToSilenceMs != null) other.push(`按下→静音 ${r.pressToSilenceMs}`);
      if (r.pressToInterruptedMs != null) other.push(`服务端确认打断 ${r.pressToInterruptedMs}`);
      if (r.bargeInCount) other.push('这一轮被打断');
      if (r.extMicCount === 1) other.push('耳机麦克风');
      if (r.micOpenMs != null) other.push(`开麦 ${r.micOpenMs}`);
      if (r.underrunCount) other.push(`断音 ${r.underrunCount} 次`);
      if (r.cerPct != null) other.push(`字错率 ${r.cerPct}%`);
      if (r.noAudio) other.push('没有声音');
    } else other.push(r.label || r.phase);
    const cells = [r.n ?? '', r.item, [r.route, r.network, r.mode].filter(Boolean).join(' / '),
      r.clientReleaseToAudibleMs ?? '', r.serverReleaseToFirstAudioMs ?? '', other.join('，')];
    cells.forEach((c, i) => { const td = document.createElement('td'); td.textContent = c; if (i === 3 || i === 4) td.className = 'n'; tr.appendChild(td); });
    tb.appendChild(tr);
  });
  // summary per item and condition
  const groups = {};
  for (const r of S.rows) if (r.kind === 'turn') (groups[`${r.item} ${r.route}/${r.network}/${r.mode}`] ||= []).push(r);
  const lines = Object.entries(groups).map(([k, rs]) => {
    const a = rs.map((r) => r.clientReleaseToAudibleMs).filter((v) => v != null);
    const sil = rs.map((r) => r.pressToSilenceMs).filter((v) => v != null);
    const cer = rs.map((r) => r.cerPct).filter((v) => v != null);
    let s = `${k}：${rs.length} 轮`;
    if (a.length) s += `，松手→出声 中位 ${pct(a, 0.5)} ms、p95 ${pct(a, 0.95)} ms`;
    if (sil.length) s += `，按下→静音 中位 ${pct(sil, 0.5)} ms、最慢 ${Math.max(...sil)} ms`;
    if (cer.length) s += `，字错率平均 ${(cer.reduce((x, y) => x + y, 0) / cer.length).toFixed(1)}%`;
    return s;
  });
  $('summary').textContent = lines.length ? '' : '还没有结果。';
  lines.forEach((l) => { const p = document.createElement('div'); p.textContent = l; $('summary').appendChild(p); });
}
function renderEnv() {
  const rows = [['浏览器', ENV.browser], ['麦克风（getUserMedia）', ENV.getUserMedia], ['WebSocket 握手带 Cookie', ENV.cookieSeen],
    ['音频会话（audioSession）', ENV.audioSession], ['采样率', ENV.sampleRate], ['输出延迟', ENV.latency],
    ['开麦耗时', ENV.micOpenMs], ['麦克风来源（自动）', ENV.micRoute], ['开始→可以说话', ENV.connectToReadyMs], ['UA', ENV.ua]];
  const tb = $('envT'); tb.textContent = '';
  for (const [k, v] of rows) { const tr = document.createElement('tr'); for (const c of [k, String(v)]) { const td = document.createElement('td'); td.textContent = c; tr.appendChild(td); } tb.appendChild(tr); }
}

// ---------------------------------------------------------------- login
async function boot() {
  load(); render(); renderEnv(); updateHint();
  let ok = false;
  try { ok = (await fetch('/v1/me', { credentials: 'same-origin' })).ok; } catch { /* offline */ }
  show('login', !ok); loggedIn(ok);
}
function loggedIn(ok) { for (const id of ['setup', 'results', 'device']) show(id, ok); }   // before login a stranger sees only the title and the code box
$('loginBtn').addEventListener('click', async () => {
  $('loginMsg').textContent = '';
  try {
    const r = await fetch('/v1/auth/login', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ inviteCode: $('code').value.trim() }) });
    if (r.ok) { $('code').value = ''; show('login', false); loggedIn(true); return; }
    const j = await r.json().catch(() => ({}));
    $('loginMsg').textContent = j.error?.message || `入れませんでした（${r.status}）`;
  } catch { $('loginMsg').textContent = 'つながりません'; }
});

// ---------------------------------------------------------------- audio
async function ensureAudio() {
  if (!S.ctx) {
    S.ctx = new AudioContext({ latencyHint: 'interactive' });
    await S.ctx.audioWorklet.addModule('capture-worklet.js');
    await S.ctx.audioWorklet.addModule('play-worklet.js');
    S.play = new AudioWorkletNode(S.ctx, 'play', { numberOfInputs: 0, outputChannelCount: [2] });
    S.play.connect(S.ctx.destination);
    S.play.port.onmessage = (e) => onPlay(e.data);
    S.cap = new AudioWorkletNode(S.ctx, 'capture', { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1] });
    const mute = S.ctx.createGain(); mute.gain.value = 0; S.cap.connect(mute).connect(S.ctx.destination);   // keeps the node pulled
    S.cap.port.onmessage = (e) => onCapture(e.data);
    ENV.sampleRate = `${S.ctx.sampleRate} Hz`;
  }
  if (S.ctx.state !== 'running') await S.ctx.resume();
  ENV.latency = `base ${Math.round((S.ctx.baseLatency || 0) * 1000)} ms / output ${Math.round((S.ctx.outputLatency || 0) * 1000)} ms`;
  renderEnv();
}
function setAudioSession(type) {
  try { if (navigator.audioSession) navigator.audioSession.type = type; } catch { /* older Safari */ }
  ENV.audioSession = navigator.audioSession ? navigator.audioSession.type : '不支持'; renderEnv();
}
async function openMic() {
  if (S.stream && S.stream.getAudioTracks().some((t) => t.readyState === 'live')) return 0;
  const t0 = performance.now();
  setAudioSession('play-and-record');
  try {
    S.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
  } catch (err) {
    ENV.getUserMedia = `失败：${err.name}`; renderEnv();
    addRow({ kind: 'event', item: sel('item'), browser: ENV.browser, device: ENV.device, phase: 'gum_denied', label: `麦克风失败 ${err.name}` });
    setAudioSession('playback');
    throw err;
  }
  S.src = S.ctx.createMediaStreamSource(S.stream); S.src.connect(S.cap);
  const label = S.stream.getAudioTracks()[0]?.label || '';      // only the class is kept, never the name
  S.extMic = label ? (/iphone|ipad|built-in|内蔵|default|既定|fake/i.test(label) ? 0 : 1) : null;
  ENV.micRoute = S.extMic == null ? '不明' : S.extMic ? '外接（耳机）' : '本机'; renderEnv(); checkRoute();
  const ms = r0(performance.now() - t0);
  if (ENV.getUserMedia !== '可以用') addRow({ kind: 'event', item: sel('item'), browser: ENV.browser, device: ENV.device, phase: 'gum_granted', micOpenMs: ms, label: `麦克风可以用（${ms} ms）` });
  ENV.getUserMedia = '可以用'; ENV.micOpenMs = `${ms} ms`; renderEnv();
  return ms;
}
function closeMic() {
  if (!S.stream) return;
  try { S.src.disconnect(); } catch { /* already */ }
  S.stream.getTracks().forEach((t) => t.stop()); S.stream = null; S.src = null;
  setAudioSession('playback');
}
function ctxToPerf(t) {
  if (S.ctx.getOutputTimestamp) {
    const ts = S.ctx.getOutputTimestamp();
    if (ts.performanceTime) return ts.performanceTime + (t - ts.contextTime) * 1000;
  }
  return performance.now() + (t - S.ctx.currentTime + (S.ctx.outputLatency || S.ctx.baseLatency || 0)) * 1000;
}
function pcm24kToCtx(buf) {
  const src = new Int16Array(buf), ratio = S.ctx.sampleRate / 24000, n = Math.round(src.length * ratio), out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const x = i / ratio, i0 = Math.floor(x), f = x - i0, a = src[i0] || 0, b = src[Math.min(src.length - 1, i0 + 1)] || 0;
    out[i] = (a + (b - a) * f) / 32768;
  }
  return out;
}
function onCapture(m) {
  $('meter').firstElementChild.style.width = `${Math.min(100, m.peak * 140)}%`;
  const t = S.turn;
  if (!S.sending || !t || !S.ws || S.ws.readyState !== 1) return;
  const now = performance.now();
  const f = new Uint8Array(5 + m.pcm.byteLength); f[0] = 0x01; new DataView(f.buffer).setUint32(1, t.turnSeq); f.set(new Uint8Array(m.pcm), 5);
  S.ws.send(f);
  if (t.firstUpAt == null) t.firstUpAt = now;
  t.upChunks = (t.upChunks || 0) + 1;
}
function onPlay(m) {
  const t = S.turn;
  if (m.flushed) {
    const f = S.flushReq; S.flushReq = null;
    if (f && f.turn && m.was) f.turn.pressToSilenceMs = r0(ctxToPerf(m.t) - f.at);
    return;
  }
  if (m.started) S.playing = true;
  if (m.drained) S.playing = false;
  if (!t || m.tag !== t.turnSeq) return;
  if (m.started && t.audibleAt == null) t.audibleAt = ctxToPerf(m.t);
  if (m.drained) { t.drains = (t.drains || 0) + 1; if (t.complete) { t.endedAfterComplete = true; finish(t); } }
}

// ---------------------------------------------------------------- connection
function send(o) { if (S.ws && S.ws.readyState === 1) S.ws.send(JSON.stringify(o)); }
$('connectBtn').addEventListener('click', connect);
$('hangBtn').addEventListener('click', hang);
async function connect() {
  $('connectBtn').disabled = true;
  try {
    await ensureAudio();
    setAudioSession('playback');
    if (sel('mode') === 'open') await openMic().catch(() => {});
    S.connectAt = performance.now(); S.ready = false; S.seq = 0;
    const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/v1/playthroughs/s1b/live`;
    const ws = new WebSocket(url); ws.binaryType = 'arraybuffer'; S.ws = ws;
    state('连接中…');
    ws.onopen = () => send({ type: 'hello', lastSeq: 0, clientVersion: 's2-voice-1' });
    ws.onmessage = (e) => (typeof e.data === 'string' ? onJson(JSON.parse(e.data)) : onBinary(e.data));
    ws.onclose = (e) => {
      if (S.ws !== ws) return;
      S.ready = false; clearInterval(S.pingTimer);
      const why = { 4001: '没有登录（握手没带 Cookie）', 4290: '连接太多', 1008: '来源不对' }[e.code] || '';
      state(`连接断开（${e.code}${why ? '，' + why : ''}）`);
      if (e.code === 4001) { ENV.cookieSeen = '没有带'; renderEnv(); addRow({ kind: 'event', item: sel('item'), browser: ENV.browser, device: ENV.device, phase: 'cookie_missing', label: '握手没带 Cookie' }); }
      show('hangBtn', false); $('connectBtn').disabled = false; show('connectBtn', true);
    };
    show('convo', true); show('connectBtn', false); show('hangBtn', true); talkLabel();
  } catch (err) {
    state(`开始失败：${err.message || err}`); $('connectBtn').disabled = false;
  }
}
function hang() {
  send({ type: 'unfocus', reason: 'menu' });
  const ws = S.ws; S.ws = null; if (ws) ws.close();
  closeMic(); S.ready = false; clearInterval(S.pingTimer);
  show('hangBtn', false); show('connectBtn', true); $('connectBtn').disabled = false; state('对话已结束');
}
function onJson(m) {
  const t = S.turn;
  switch (m.type) {
    case 'welcome':
      ENV.cookieSeen = m.cookieSeen ? '带了' : '没有带'; renderEnv();
      addRow({ kind: 'event', item: sel('item'), browser: ENV.browser, device: ENV.device, phase: m.cookieSeen ? 'cookie_seen' : 'cookie_missing', label: m.cookieSeen ? '握手带了 Cookie' : '握手没带 Cookie' });
      if (!m.voice?.enabled) state('语音现在不可用（已达到上限或服务关闭）');
      send({ type: 'near', character: CHARACTER });
      send({ type: 'focus', character: CHARACTER });
      clearInterval(S.pingTimer); S.pingTimer = setInterval(() => send({ type: 'ping' }), 20000);
      break;
    case 'session_preparing': state('メロスが振り向いています…'); break;
    case 'session_ready':
      if (!S.ready) { const ms = r0(performance.now() - S.connectAt); ENV.connectToReadyMs = `${ms} ms`; renderEnv(); addRow({ kind: 'event', item: sel('item'), browser: ENV.browser, network: sel('network'), device: ENV.device, phase: 'ready', connectToReadyMs: ms, label: `开始→可以说话 ${ms} ms` }); }
      S.ready = true; state(m.voiceAvailable === false ? '语音不可用，可以用文字' : '可以说话了');
      break;
    case 'transcript': line(m); break;
    case 'interrupted': if (t && t.interrupting && t.pressToInterruptedMs == null) t.pressToInterruptedMs = r0(performance.now() - t.pressAt); break;
    case 'turn_complete': {
      const tc = S.byId.get(m.turnId);
      if (tc && !tc.complete) { const t = tc;
        // all of the reply's audio frames came before this message; a stop in playback after it is the end,
        // a stop before it was a gap (underrun)
        t.complete = true; t.noAudio = !m.audio; t.drainsAtComplete = t.drains || 0;
        t.serverReleaseToFirstAudioMs = m.metrics?.serverReleaseToFirstAudioMs ?? null;
        if (t.audibleAt != null && !S.playing) t.endedBeforeComplete = true;
        finish(t); setTimeout(() => finish(t, true), 30000);
      }
      break;
    }
    case 'degraded': state(`语音降级：${m.reason}`); break;
    case 'goaway': state('服务端要求重连（30 分钟上限）'); break;
    case 'error': state(`错误：${m.error?.message || m.error?.code}`); break;
    default: break;
  }
}
function onBinary(buf) {
  const u8 = new Uint8Array(buf);
  if (u8[0] !== 0x02 || buf.byteLength < 6) return;
  const seq = new DataView(buf).getUint32(1), t = S.turn;
  if (!t || seq !== t.turnSeq) return;                       // an old turn's reply: dropped
  if (t.firstDownAt == null) t.firstDownAt = performance.now();
  const f = pcm24kToCtx(buf.slice(5));
  S.play.port.postMessage({ pcm: f.buffer, tag: seq }, [f.buffer]);
}
function line(m) {
  const box = $('lines'), id = `l-${m.turnId}-${m.speaker}`;
  let p = document.getElementById(id);
  if (!p) {
    p = document.createElement('p'); p.id = id;
    const reply = m.speaker === 'player' && document.getElementById(`l-${m.turnId}-${CHARACTER}`);
    if (reply) box.insertBefore(p, reply); else box.appendChild(p);   // the player's text can arrive after the reply
  }
  p.className = (m.speaker === 'player' ? 'me' : '') + (m.final ? '' : ' partial');
  p.textContent = (m.speaker === 'player' ? 'あなた：' : 'メロス：') + m.text;
  box.scrollTop = box.scrollHeight;
  const t = S.byId.get(m.turnId);
  if (t && m.speaker === 'player' && m.final) { t.heard = m.text; finish(t); }
}

// ---------------------------------------------------------------- turns
function newTurn(mode) {
  const seq = ++S.seq;
  const t = { kind: 'turn', n: S.rows.filter((r) => r.kind === 'turn').length + 1, turnId: `t${Date.now().toString(36)}-${seq}`, turnSeq: seq,
    item: sel('item'), route: sel('route'), network: sel('network'), mode, browser: ENV.browser, device: ENV.device, pressAt: performance.now() };
  if (S.extMic != null) t.extMicCount = S.extMic;   // 1 = the live mic is not the phone's own (Bluetooth / wired headset)
  if (t.item === 't5') { const g = whisperGroup(); t.phase = `${g[0]}${String(S.whisperIdx + 1).padStart(2, '0')}`; t.expected = WHISPER[g][S.whisperIdx]; }
  S.byId.set(t.turnId, t); if (S.byId.size > 20) S.byId.delete(S.byId.keys().next().value);
  return t;
}
async function press(e) {
  e.preventDefault();
  if (S.pressed || !S.ws || S.ws.readyState !== 1) return;
  if (!condOk()) { talkLabel(); state('先选「出声 / 网络 / 麦克风」，再按'); return; }
  S.pressed = true; $('talk').classList.add('on'); $('talk').textContent = '話しています（離すと送信）';
  try { $('talk').setPointerCapture(e.pointerId); } catch { /* synthetic */ }
  const prev = S.turn, t = newTurn(sel('mode'));
  if (prev && (S.playing || (prev.releaseAt && !prev.complete))) {         // barge-in: stop locally first, then tell the server
    t.interrupting = true; S.flushReq = { at: t.pressAt, turn: t }; S.play.port.postMessage({ flush: true });
    prev.bargeInCount = 1;
    if (prev.complete) finish(prev);
    else prev.bargeTimer = setTimeout(() => { prev.complete = true; finish(prev); }, 5000);   // its turn_complete may never come
  }
  S.turn = t;
  send({ type: 'activity_start', turnId: t.turnId, turnSeq: t.turnSeq });
  if (t.mode === 'perturn') { try { t.micOpenMs = await openMic(); } catch { release(); return; } }
  S.sending = true;
}
function release() {
  if (!S.pressed) return;
  S.pressed = false; $('talk').classList.remove('on'); talkLabel();
  const t = S.turn; S.sending = false; if (!t) return;
  t.releaseAt = performance.now();
  send({ type: 'activity_end', turnId: t.turnId, turnSeq: t.turnSeq });
  if (t.mode === 'perturn') closeMic();
  state('メロスが考えています…');
}
$('talk').addEventListener('pointerdown', press);
$('talk').addEventListener('pointerup', release);
$('talk').addEventListener('pointercancel', release);
$('talk').addEventListener('contextmenu', (e) => e.preventDefault());
$('sendText').addEventListener('click', () => {
  const text = $('textIn').value.trim(); if (!text || !S.ws) return;
  const t = newTurn('text'); S.turn = t; t.releaseAt = performance.now(); $('textIn').value = '';
  send({ type: 'text', turnId: t.turnId, turnSeq: t.turnSeq, text });
});
function finish(t, timeout = false) {
  if (t.done || !t.complete) return;
  const ended = t.noAudio || t.endedBeforeComplete || t.endedAfterComplete || t.bargeInCount === 1;
  if (!timeout && (!ended || (t.expected && t.heard == null))) return;   // wait for playback to end and, for item 5, the heard text
  t.done = true; clearTimeout(t.bargeTimer);
  const d = (a, b) => (a != null && b != null ? r0(a - b) : null);
  Object.assign(t, {
    speechMs: d(t.releaseAt, t.pressAt), pressToFirstUpMs: d(t.firstUpAt, t.pressAt),
    clientReleaseToFirstDownMs: d(t.firstDownAt, t.releaseAt), clientReleaseToAudibleMs: d(t.audibleAt, t.releaseAt),
    firstDownToAudibleMs: d(t.audibleAt, t.firstDownAt), upChunkCount: t.upChunks || 0,
    underrunCount: t.endedAfterComplete ? t.drainsAtComplete : Math.max(0, (t.drainsAtComplete || 0) - 1),
  });
  if (t.clientReleaseToFirstDownMs != null && t.serverReleaseToFirstAudioMs != null) t.netMs = t.clientReleaseToFirstDownMs - t.serverReleaseToFirstAudioMs;
  if (t.expected && t.heard != null) t.cerPct = Math.round(1000 * cer(t.expected, t.heard)) / 10;
  if (timeout && !ended) t.timeoutCount = 1;
  t.n = S.rows.filter((r) => r.kind === 'turn').length + 1;   // numbered when recorded: an interrupted turn finishes after the next one starts
  const row = { ...t };
  for (const k of ['pressAt', 'releaseAt', 'firstUpAt', 'firstDownAt', 'audibleAt', 'drains', 'drainsAtComplete', 'upChunks', 'complete', 'done',
    'endedBeforeComplete', 'endedAfterComplete', 'interrupting', 'heard', 'expected', 'bargeTimer']) delete row[k];
  addRow(row);
  if (t.item === 't5' && S.turn === t) { S.whisperIdx = (S.whisperIdx + 1) % 5; showSay(); }
  if (S.turn === t) state(t.noAudio ? '这一轮没有声音' : '可以说话了');
}
function cer(ref, hyp) {   // character error rate; drops the same characters as the proxy side's cerIgnore
  const clean = (s) => [...s.replace(/[\s\u3000、。，．,.!?！？「」『』（）()・…ー〜~]/g, '')];
  const a = clean(ref), b = clean(hyp);
  if (!a.length) return 0;
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    prev = cur;
  }
  return prev[b.length] / a.length;
}

// ---------------------------------------------------------------- items, ratings, whisper sentences
function updateHint() {
  const it = sel('item');
  $('hint').textContent = HINTS[it];
  show('sayBox', it === 't5'); showSay();
  const old = document.getElementById('ratings'); if (old) old.remove();
  if (RATINGS[it]) {
    const row = document.createElement('div'); row.id = 'ratings'; row.className = 'row'; row.style.marginTop = '6px';
    for (const [v, label] of RATINGS[it]) {
      const b = document.createElement('button'); b.textContent = label;
      b.addEventListener('click', () => addRow({ kind: 'event', item: it, route: sel('route'), network: sel('network'), mode: sel('mode'), browser: ENV.browser, device: ENV.device, phase: v, label }));
      row.appendChild(b);
    }
    $('hint').after(row);
  }
}
function showSay() {
  const g = whisperGroup();
  $('say').textContent = WHISPER[g][S.whisperIdx];
  $('sayIdx').textContent = `${g === 'phone' ? '手机麦克风' : '耳机麦克风'} ${S.whisperIdx + 1} / 5`;
}
$('item').addEventListener('change', () => {   // a new test item asks for 出声 / 网络 / 麦克风 again (iPhone Safari can't tell the network type)
  for (const id of COND) $(id).value = '';
  updateHint(); talkLabel();
});
$('route').addEventListener('change', () => { S.whisperIdx = 0; showSay(); talkLabel(); });
$('network').addEventListener('change', talkLabel);
$('mode').addEventListener('change', async () => {   // switching while connected opens or closes the mic now
  talkLabel();
  if (!S.ws || S.ws.readyState !== 1) return;
  if (sel('mode') === 'open') await openMic().catch(() => {}); else closeMic();
});
$('prevSay').addEventListener('click', () => { S.whisperIdx = (S.whisperIdx + 4) % 5; showSay(); });
$('nextSay').addEventListener('click', () => { S.whisperIdx = (S.whisperIdx + 1) % 5; showSay(); });

// ---------------------------------------------------------------- background and back (item 7)
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { S.hiddenAt = performance.now(); return; }
  if (!S.hiddenAt || !S.ctx) return;
  const away = r0(performance.now() - S.hiddenAt); S.hiddenAt = 0;
  const micDead = S.stream && S.stream.getAudioTracks().every((t) => t.readyState !== 'live');
  const wsDead = !S.ws || S.ws.readyState !== 1;
  S.away = { awayMs: away, micDead, wsDead, ctxState: S.ctx.state };
  if (S.ctx.state !== 'running' || micDead || wsDead) { show('resumeBox', true); state(`回来了（离开 ${Math.round(away / 1000)} 秒）：音频 ${S.ctx.state}${micDead ? '，麦克风已断' : ''}${wsDead ? '，连接已断' : ''}`); }
  else addRow({ kind: 'event', item: 't7', browser: ENV.browser, device: ENV.device, phase: 'resume_ok', awayMs: away, resumeMs: 0, label: `离开 ${Math.round(away / 1000)} 秒，回来时不用点就能用` });
});
$('resumeBtn').addEventListener('click', async () => {
  const t0 = performance.now(), a = S.away || {};
  try { await S.ctx.resume(); } catch { /* try again */ }
  if (a.micDead && sel('mode') === 'open') { closeMic(); await openMic().catch(() => {}); }
  const resumeMs = r0(performance.now() - t0);
  if (a.wsDead) { await connect(); }
  show('resumeBox', false);
  addRow({ kind: 'event', item: 't7', browser: ENV.browser, device: ENV.device, phase: a.wsDead ? 'resume_reconnect' : 'resume_tap', awayMs: a.awayMs, resumeMs, label: `离开 ${Math.round((a.awayMs || 0) / 1000)} 秒，点一下恢复 ${resumeMs} ms（音频原来是 ${a.ctxState}${a.micDead ? '，麦克风断了' : ''}${a.wsDead ? '，连接断了，已重连' : ''}）` });
});

// ---------------------------------------------------------------- export
$('copyBtn').addEventListener('click', async () => {
  const text = JSON.stringify({ page: 's2-voice-1', env: ENV, rows: S.rows }, null, 1);
  try { await navigator.clipboard.writeText(text); $('copyBtn').textContent = '已复制'; }
  catch { show('dump', true); $('dump').value = text; $('dump').select(); $('copyBtn').textContent = '请手动复制下面的文字'; }
  setTimeout(() => { $('copyBtn').textContent = '复制全部结果'; }, 2500);
});
$('clearBtn').addEventListener('click', () => { if (confirm('清空这台设备上的结果？（已经上报到服务端的不受影响）')) { S.rows = []; save(); render(); } });

boot();
