"""Test audio for the lip-sync demo: two of Melos's lines and five sustained vowels.

/tmp/ojtenv/bin/python -I gen_voice.py out_dir
Open JTalk (pyopenjtalk-plus, MIT) with the bundled HTS voice "Mei" (CC BY 3.0, Nagoya
Institute of Technology), pitched down. Test page only: the product speaks with Gemini Live.
Writes 24 kHz mono 16-bit WAVs and voice.json (texts, kana, vowel segment times).
"""
import json
import os
import sys
import wave

import numpy as np
import pyopenjtalk

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
SR = 24000
LINES = ['市を暴君の手から救うのだ。', '私は、ちゃんと死ぬる覚悟で居るのに。命乞いなど決してしない。']
VOWELS = [('a', 'あああ'), ('i', 'いいい'), ('u', 'ううう'), ('e', 'えええ'), ('o', 'おおお')]
SPEED, HALF = 0.95, -5.0


def synth(text):
    x, sr = pyopenjtalk.tts(text, speed=SPEED, half_tone=HALF)
    n = int(len(x) * SR / sr)
    # linear resample is enough for a mouth test; 48k -> 24k
    y = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
    return y / 32768.0


def save(name, y):
    y = np.clip(y / max(1e-6, np.abs(y).max()) * 0.85, -1, 1)
    with wave.open(os.path.join(out, name), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((y * 32767).astype('<i2').tobytes())
    return len(y) / SR


meta = {'sr': SR, 'voice': 'Open JTalk + HTS voice Mei (CC BY 3.0), pitch -5', 'lines': [], 'vowels': []}
for i, t in enumerate(LINES):
    dur = save(f'line{i + 1}.wav', synth(t))
    meta['lines'].append({'file': f'line{i + 1}.wav', 'text': t, 'kana': pyopenjtalk.g2p(t, kana=True), 'sec': round(dur, 3)})

# vowels in one file: each sustained vowel, 0.25 s gap; keep the steady middle 60 % of each for templates
parts, t0 = [], 0.0
gap = np.zeros(int(0.25 * SR))
for v, text in VOWELS:
    y = synth(text)
    env = np.abs(y)
    k = np.convolve(env, np.ones(480) / 480, 'same')
    on = np.nonzero(k > 0.15 * k.max())[0]
    a, b = on[0], on[-1]
    seg = y[a:b]
    s = t0 + 0.2 * len(seg) / SR
    e = t0 + 0.8 * len(seg) / SR
    meta['vowels'].append({'v': v, 'start': round(s, 3), 'end': round(e, 3)})
    parts += [seg, gap]
    t0 += (len(seg) + len(gap)) / SR
whole = np.concatenate(parts)
save('vowels.wav', whole)
with open(os.path.join(out, 'voice.json'), 'w') as f:
    json.dump(meta, f, ensure_ascii=False, indent=1)
print(json.dumps(meta, ensure_ascii=False, indent=1))
