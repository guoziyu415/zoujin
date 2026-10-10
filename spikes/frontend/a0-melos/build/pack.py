"""Assemble the A-0 test page folder.

python3 pack.py <s7_page_dir> <phone_glb_dir> <voice_dir> <out_dir>
(voice_dir: gen_voice.py output with lines/ from gen_lines.py inside)
Binary files become base64 JS modules (artifact pages serve standard web types only);
plaza geometry, textures and AO lightmaps are reused from the S7 page.
"""
import base64
import hashlib
import json
import os
import re
import shutil
import sys
import time

s7, glbs, voice, out = sys.argv[1:5]
here = os.path.dirname(os.path.abspath(__file__))
for d in ('data', 'tex', 'lm'):
    os.makedirs(os.path.join(out, d), exist_ok=True)


def b64mod(src, name):
    raw = open(src, 'rb').read()
    with open(os.path.join(out, 'data', name + '.js'), 'w') as f:
        f.write('export default "' + base64.b64encode(raw).decode() + '";\n')
    return len(raw), hashlib.sha256(raw).hexdigest()[:12]


sizes, shas = {}, {}
for m in ('talk_std', 'talk_high', 'walk', 'anims'):
    sizes[m], shas[m] = b64mod(os.path.join(glbs, m + '.glb'), m)
# vowels.wav (Open JTalk test voice) only calibrates the vowel templates; the lines are the
# Melos candidate voices from the casting run (gen_lines.py), MP3
vmeta = json.load(open(os.path.join(voice, 'voice.json')))
lmeta = json.load(open(os.path.join(voice, 'lines', 'lines.json')))
sizes['voice'], _ = b64mod(os.path.join(voice, 'vowels.wav'), 'vowels')
# D-025: Melos = Fenrir; the other casting candidate stays in lines/ but not in the page
lmeta['voices'] = {v: ls for v, ls in lmeta['voices'].items() if v == 'Fenrir'}
for v, ls in lmeta['voices'].items():
    for k in ls:
        b, _ = b64mod(os.path.join(voice, 'lines', f'{v.lower()}_{k}.mp3'), f'v_{v.lower()}_{k}')
        sizes['voice'] += b
shutil.copy(os.path.join(s7, 'data', 'plaza_geo.js'), os.path.join(out, 'data', 'plaza_geo.js'))
for f in os.listdir(os.path.join(s7, 'tex')):
    if f.endswith('_hi.jpg'):
        shutil.copy(os.path.join(s7, 'tex', f), os.path.join(out, 'tex', f))
for f in ('ground_ao_1024.jpg', 'arch_ao_1024.jpg'):
    shutil.copy(os.path.join(s7, 'lm', f), os.path.join(out, 'lm', f))

manifest = {'build': time.strftime('%Y%m%d-%H%M'), 'sizes': sizes, 'sha': shas,
            'voice': {'voices': lmeta['voices'], 'vowels': vmeta['vowels']}}
src = open(os.path.join(here, 'page', 'index.src.html')).read()
html = src.replace('/*MANIFEST*/{}', '/*MANIFEST*/' + json.dumps(manifest, ensure_ascii=False))
assert html != src
open(os.path.join(out, 'index.html'), 'w').write(html)
total = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(out) for f in fs)
print(json.dumps(manifest['sizes']), shas, 'folder', round(total / 1048576, 2), 'MB')
