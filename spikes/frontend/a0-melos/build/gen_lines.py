"""Build the three test lines UX asked for (A-0 acceptance 1.2) from the casting recordings
of the Melos candidate voices (MP3: every browser decodes it, AAC fails in open-source Chromium): a short aizuchi (<= 0.5 s), one of about 3 s, and one of
8 s or more with pauses. Cuts and order as UX specified on 10-10. The recordings are Gemini Live output from the S-1 casting run
(ux/casting-audio/casting/clips/melos/<voice>/); they are only used on this test page.

python3 gen_lines.py <casting clips dir> <out dir> [voice ...]
"""
import json
import os
import subprocess
import sys
import wave

import numpy as np

SR = 24000
src, out = sys.argv[1], sys.argv[2]
voices = sys.argv[3:] or ['Fenrir', 'Puck']
os.makedirs(out, exist_ok=True)


def read(path):
    with wave.open(path) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1 and w.getsampwidth() == 2
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def env_db(x, hop=0.01):
    n = int(SR * hop)
    k = len(x) // n
    r = np.sqrt((x[:k * n].reshape(k, n) ** 2).mean(1) + 1e-12)
    return 20 * np.log10(r)


def trim(x, floor=-45):
    """Cut leading and trailing silence, keep 40 ms either side."""
    db = env_db(x)
    on = np.nonzero(db > floor)[0]
    a, b = max(0, on[0] - 4), min(len(db), on[-1] + 5)
    return x[a * 240:b * 240]


def first_word(x, floor=-40, gap=0.06):
    """Up to the first pause of at least `gap` seconds after speech starts (いや、... -> いや)."""
    x = trim(x)
    db = env_db(x)
    on = db > floor
    i = np.argmax(on)
    run = 0
    for j in range(i + 10, len(on)):
        run = run + 1 if not on[j] else 0
        if run * 0.01 >= gap:
            end = j - run + 1
            return x[:min(len(x), (end + 3) * 240)]
    return x


# end of 「いや」 in each voice's own2, measured by UX (10-10); the cut falls in the following silence
IYA_END = {'Fenrir': 0.48, 'Puck': 0.30}


def aizuchi(x, voice):
    db = env_db(x)
    start = max(0, int(np.argmax(db > -45)) - 2) * 240
    end = int(IYA_END[voice] * SR) if voice in IYA_END else len(first_word(x))
    y = x[start:end].copy()
    n = int(SR * 0.01)
    y[-n:] *= np.linspace(1, 0, n)          # 10 ms fade-out
    return y


def silence(s):
    return np.zeros(int(SR * s), np.float32)


def fade(x, ms=8):
    n = int(SR * ms / 1000)
    x = x.copy()
    x[:n] *= np.linspace(0, 1, n)
    x[-n:] *= np.linspace(1, 0, n)
    return x


def norm(x, peak_db=-3):
    return x * (10 ** (peak_db / 20) / (np.abs(x).max() + 1e-9))


def write(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


meta = {'source': 'S-1 casting recordings (Gemini Live), ux/casting-audio/casting/clips/melos', 'voices': {}}
for v in voices:
    d = os.path.join(src, v)
    c = {k: read(os.path.join(d, k + '.wav')) for k in ('own1', 'own2', 'own3', 'n1')}
    # each line: list of (audio, subtitle) pieces with pauses between them; the page shows
    # one subtitle per piece, switched at the time the piece starts
    # UX (10-10): all three sentences in Melos's own voice (n1 is desu/masu, out of character);
    # the natural pauses inside own2 / own1 / own3 show whether the mouth closes in a pause
    long_parts = [(fade(trim(c['own2'])), 'いや、まだ陽は沈まぬ。'), (silence(0.7), None),
                  (fade(trim(c['own3'])), '信じられているから走るのだ。'), (silence(0.7), None),
                  (fade(trim(c['own1'])), '人の心を疑うのは、最も恥ずべき悪徳だ。')]
    lines = {
        's': [(fade(aizuchi(c['own2'], v)), 'いや。')],
        'm': [(fade(trim(c['own2'])), 'いや、まだ陽は沈まぬ。')],
        'l': long_parts,
    }
    meta['voices'][v] = {}
    for k, parts in lines.items():
        segs, t = [], 0.05
        for x, text in parts:
            if text:
                segs.append([round(t, 2), text])
            t += len(x) / SR
        text = '……'.join(sg[1].rstrip('。') + '。' for sg in segs) if len(segs) > 1 else segs[0][1]
        x = np.concatenate([silence(0.05), norm(np.concatenate([a for a, _ in parts])), silence(0.05)])
        base = os.path.join(out, f'{v.lower()}_{k}')
        write(base + '.wav', x)
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', base + '.wav', '-c:a', 'libmp3lame', '-b:a', '64k',
                        '-ac', '1', base + '.mp3'], check=True)
        meta['voices'][v][k] = {'text': text, 'segments': segs, 'seconds': round(len(x) / SR, 2),
                                'bytes': os.path.getsize(base + '.mp3')}
with open(os.path.join(out, 'lines.json'), 'w') as f:
    json.dump(meta, f, ensure_ascii=False, indent=1)
print(json.dumps(meta, ensure_ascii=False, indent=1))
