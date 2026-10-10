"""Offline check of the page's vowel classifier (same MFCC + templates as the JS) on the test lines.
python3 lipcheck.py voice"""
import json, sys, wave
import numpy as np
d = sys.argv[1]; meta = json.load(open(f'{d}/voice.json'))
SR = 48000; N = 1024
def load(f):
    w = wave.open(f'{d}/{f}'); x = np.frombuffer(w.readframes(w.getnframes()), '<i2') / 32768.0
    return np.interp(np.arange(0, len(x) * 2) / 2, np.arange(len(x)), x)   # 24k -> 48k like the browser
M, C = 26, 12
mel = lambda f: 2595 * np.log10(1 + f / 700); inv = lambda m: 700 * (10 ** (m / 2595) - 1)
pts = inv(np.linspace(mel(80), mel(7600), M + 2)); b = pts * N / SR
bank = np.zeros((M, N // 2))
for m in range(M):
    for k in range(int(np.floor(b[m])), min(int(np.ceil(b[m + 2])) + 1, N // 2)):
        v = (k - b[m]) / (b[m + 1] - b[m]) if k < b[m + 1] else (b[m + 2] - k) / (b[m + 2] - b[m + 1])
        if v > 0: bank[m, k] = v
win = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(N) / (N - 1))
dct = np.array([[np.cos(np.pi * n * (m + 0.5) / M) for m in range(M)] for n in range(1, C + 1)])
def feat(fr):
    rms = np.sqrt((fr ** 2).mean()); X = np.fft.fft(fr * win)[:N // 2]; e = bank @ (np.abs(X) ** 2)
    return rms, dct @ np.log(e + 1e-9)
vw = load('vowels.wav'); T = {}
for s in meta['vowels']:
    fs = [feat(vw[i:i + N])[1] for i in range(int(s['start'] * SR), int(s['end'] * SR) - N, 480)]
    T[s['v']] = np.mean(fs, 0)
# template separation: nearest other vowel distance
for v in T: print(v, 'nearest other', min((np.linalg.norm(T[v] - T[u]), u) for u in T if u != v))
for L in meta['lines']:
    x = load(L['file']); seq = []
    for i in range(0, len(x) - N, 960):          # 20 ms hop
        rms, c = feat(x[i:i + N]); db = 20 * np.log10(rms + 1e-9); op = np.clip((db + 42) / 24, 0, 1)
        if op < 0.05: seq.append('_'); continue
        dd = {v: np.sum((c - t) ** 2) for v, t in T.items()}; w = {v: 1 / (dd[v] ** 2 + 1e-6) for v in dd}; s = sum(w.values())
        best = max(w, key=w.get); seq.append(best if w[best] / s > 0.5 else best.upper() if False else best)
    # collapse runs
    out = []; [out.append(ch) for ch in seq if not out or out[-1] != ch]
    print(L['kana']); print(''.join(seq)); print('runs:', ''.join(out))

print('--- with cepstral mean normalisation (templates minus their mean; live minus a running voiced mean)')
TM = np.mean(list(T.values()), 0); Tn = {v: t - TM for v, t in T.items()}
for L in meta['lines']:
    x = load(L['file']); seq = []; run = TM.copy()
    for i in range(0, len(x) - N, 960):
        rms, c = feat(x[i:i + N]); db = 20 * np.log10(rms + 1e-9); op = np.clip((db + 42) / 24, 0, 1)
        if op < 0.05: seq.append('_'); continue
        run += (c - run) * 0.05
        cn = c - run
        dd = {v: np.sum((cn - t) ** 2) for v, t in Tn.items()}
        seq.append(min(dd, key=dd.get))
    out = []; [out.append(ch) for ch in seq if not out or out[-1] != ch]
    print(L['kana']); print(''.join(seq)); print('runs:', ''.join(out))
