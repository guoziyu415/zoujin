# pack S7 assets into the publish folder and inject the manifest into index.html
import os, json, base64, subprocess, shutil, glob
import numpy as np
from PIL import Image
B = '/tmp/spk/s7build'; O = '/tmp/spk/s7out'; P = '/tmp/spk/s7page'
for d in ('tex', 'lm', 'data'):
    os.makedirs(f'{P}/{d}', exist_ok=True)

# 1. textures (JPEG, two sizes)
T = f'{B}/tex'
names = ['floor_base', 'floor_nrm', 'ashlar_base', 'ashlar_nrm', 'ashlar2_base', 'plain_base', 'plain_nrm', 'plaster_base',
         'roofwarm_base', 'roof_nrm', 'doors_base', 'doors_nrm', 'cornice_base', 'cornice_nrm', 'trim_base', 'trim_nrm',
         'fabric_red_base', 'fabric_red_nrm', 'fabric_blue_base', 'hill_base', 'bark_base', 'cypress_base', 'ivy_nrm']
tex_sizes = {'lo': 0, 'hi': 0}
for n in names:
    src = next(p for p in (f'{T}/{n}.jpg', f'{T}/{n}.png') if os.path.exists(p))
    im = Image.open(src).convert('RGB')
    for tag, s in (('lo', 512), ('hi', 1024)):
        out = f'{P}/tex/{n}_{tag}.jpg'
        im.resize((s, s), Image.LANCZOS).save(out, quality=90 if n.endswith('_nrm') else 85, optimize=True)
        tex_sizes[tag] += os.path.getsize(out)

# 2. lightmaps
lm_sizes = {'1024': 0, '2048': 0}
for mesh in ('ground', 'arch'):
    for kind in ('full', 'indirect'):
        im = Image.open(f'{B}/lm_{mesh}_{kind}.png').convert('RGB')
        for s in (1024, 2048):
            out = f'{P}/lm/{mesh}_{kind}_{s}.jpg'
            (im if im.size[0] == s else im.resize((s, s), Image.LANCZOS)).save(out, quality=90, optimize=True)
            if kind == 'indirect':
                lm_sizes[str(s)] += os.path.getsize(out)
    ao = Image.open(f'{B}/lm_{mesh}_ao.png').convert('L').resize((1024, 1024), Image.LANCZOS)
    ao.save(f'{P}/lm/{mesh}_ao_1024.jpg', quality=90, optimize=True)
sd = np.load(f'{B}/bake_ground_sundirect.npy') @ np.array([0.2126, 0.7152, 0.0722])
sd = sd / max(1e-6, np.percentile(sd, 99.5))
Image.fromarray((np.clip(sd, 0, 1) * 255).astype(np.uint8)[::-1], 'L').resize((256, 256), Image.BILINEAR).save(f'{P}/lm/ground_sunmask.png', optimize=True)

# 3. binary payloads as base64 JS modules (the host refuses .glb / .hdr)
def b64js(src, dst):
    s = base64.b64encode(open(src, 'rb').read()).decode()
    open(dst, 'w').write('export default "' + s + '";\n')
    return os.path.getsize(src)
sizes = {}
sizes['sky'] = b64js(f'{B}/sky_sunset.hdr', f'{P}/data/sky.js')
sizes['geo'] = b64js(f'{O}/plaza_geo.glb', f'{P}/data/plaza_geo.js')
sizes['geoMeshopt'] = os.path.getsize(f'{O}/plaza_geo.meshopt.glb')
for tag in ('8k', '12k', '28k'):
    b64js(f'{O}/person_{tag}.q.glb', f'{P}/data/person_{tag}.js')
    sizes[f'chr{tag}'] = os.path.getsize(f'{O}/person_{tag}.meshopt.glb')
    sizes[f'chr{tag}q'] = os.path.getsize(f'{O}/person_{tag}.q.glb')
sizes['anims'] = b64js(f'{O}/anims.glb', f'{P}/data/anims.js')
k2 = {}
for f in sorted(glob.glob(f'{O}/ktx2/*.ktx2')):
    k2[os.path.basename(f)[:-5]] = base64.b64encode(open(f, 'rb').read()).decode()
open(f'{P}/data/ktx2.js', 'w').write('export default ' + json.dumps(k2) + ';\n')
sizes['texKtx2'] = sum(os.path.getsize(f) for f in glob.glob(f'{O}/ktx2/*.ktx2'))
sizes['texLo'] = tex_sizes['lo']; sizes['texHi'] = tex_sizes['hi']
sizes['lm1024'] = lm_sizes['1024']; sizes['lm2048'] = lm_sizes['2048']

meta = json.load(open(f'{B}/lm_meta.json'))
manifest = {'lightmaps': meta, 'groundLocalBounds': [-40, 34, -32, 36], 'sizes': sizes}
html = open(f'{P}/index.html').read()
import re
html = re.sub(r'const MANIFEST = /\*MANIFEST\*/\{.*?\};', 'const MANIFEST = /*MANIFEST*/' + json.dumps(manifest) + ';', html, flags=re.S)
open(f'{P}/index.html', 'w').write(html)
print(json.dumps(manifest, indent=1))
tot = 0
for root, _, fs in os.walk(P):
    for f in fs:
        tot += os.path.getsize(os.path.join(root, f))
print('publish folder total', round(tot / 1048576, 2), 'MB')
