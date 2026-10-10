# encode baked float lightmaps into 8-bit PNGs for three.js
# full / indirect: sRGB-encoded, value = baked * (1/K)  ->  three: lightMapIntensity = PI * K
# ao: linear grayscale
import numpy as np, json, sys
from PIL import Image, ImageFilter
OUT = '/tmp/spk/s7build'
meta = {}
for name in ('ground', 'arch'):
    full = np.load(f'{OUT}/bake_{name}_full.npy')
    sund = np.load(f'{OUT}/bake_{name}_sundirect.npy')
    ao = np.load(f'{OUT}/bake_{name}_ao.npy')
    ind = np.clip(full - sund, 0, None)
    def enc(a, K):
        a = np.clip(a / K, 0, 1)
        s = np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(a, 1 / 2.4) - 0.055)
        return (s * 255 + 0.5).astype(np.uint8)[::-1]   # blender rows are bottom-up
    lum = full @ np.array([0.2126, 0.7152, 0.0722])
    K = float(np.percentile(lum[lum > 1e-4], 99.7)) * 1.15
    Ki = float(np.percentile((ind @ np.array([0.2126, 0.7152, 0.0722]))[lum > 1e-4], 99.7)) * 1.15
    for tag, arr, k in (('full', full, K), ('indirect', ind, Ki)):
        im = Image.fromarray(enc(arr, k), 'RGB').filter(ImageFilter.GaussianBlur(0.7))
        im.save(f'{OUT}/lm_{name}_{tag}.png', optimize=True)
    a = np.clip(ao.mean(axis=2), 0, 1)
    Image.fromarray((a * 255 + 0.5).astype(np.uint8)[::-1], 'L').filter(ImageFilter.GaussianBlur(0.7)).save(f'{OUT}/lm_{name}_ao.png', optimize=True)
    meta[name] = {'K_full': K, 'K_indirect': Ki, 'res': full.shape[0]}
    print(name, 'K_full', round(K, 3), 'K_ind', round(Ki, 3), 'mean full', full.mean(axis=(0, 1)), 'mean ind', ind.mean(axis=(0, 1)), 'mean ao', a.mean())
json.dump(meta, open(f'{OUT}/lm_meta.json', 'w'), indent=1)
