"""Melos's clothes texture: one 1024 colour map and one normal map for the `Tunic` object (A-0 step 2).

python3 melos_tex.py <out_dir>   ->  tunic_base.png (sRGB), tunic_nrm.png (tangent space, OpenGL +Y)

UV regions as in melos_clothes.py: undyed wool (u 0..0.75), and in the right quarter the ochre belt (v 0..0.4),
the leather straps (v 0.4..0.7) and the soles (v 0.7..1).  Colours: art-direction 5.4 (Melos: ochre and undyed
wool; natural dyes, low saturation).  Generated from a fixed seed, no downloads, so the output is reproducible.
The wool has a plain weave of about 1.5 mm threads at 1024 over the tunic (the smart-project islands are roughly
1:1 in texel density), slow mottling, and a few darker slubs; folds come from the normal map's low frequencies.
"""

import os
import sys

import numpy as np
from PIL import Image

S = 1024
WOOL = (198, 186, 160)
OCHRE = (160, 98, 50)
LEATHER = (92, 60, 38)
SOLE = (70, 46, 30)


def lin(c):
    return (np.asarray(c, np.float32) / 255.0) ** 2.2


def blur(a, r):
    k = np.ones(2 * r + 1, np.float32) / (2 * r + 1)
    for ax in (0, 1):
        a = np.apply_along_axis(lambda x: np.convolve(np.pad(x, r, mode="wrap"), k, mode="valid"), ax, a)
    return a


def noise(rng, cell, r):
    n = rng.normal(0, 1, (S // cell + 1, S // cell + 1)).astype(np.float32)
    return blur(np.kron(n, np.ones((cell, cell), np.float32))[:S, :S], r)


def main(out):
    os.makedirs(out, exist_ok=True)
    rng = np.random.default_rng(20261010)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    v = 1.0 - yy / S  # image row 0 is v = 1
    right = xx >= 0.75 * S

    # height field: weave (period 3 px), slubs, mottling, broad folds
    weave = np.sin(xx * 2 * np.pi / 3) * np.sin(yy * 2 * np.pi / 3)
    slub = np.clip(noise(rng, 4, 1) - 1.6, 0, None)
    mott = noise(rng, 32, 9)
    folds = noise(rng, 96, 30)
    h_wool = 0.35 * weave + 0.8 * slub + 2.5 * folds
    h_leather = 0.6 * noise(rng, 6, 2) + 1.5 * noise(rng, 64, 16)
    h = np.where(right, h_leather, h_wool)

    # colour
    base = np.where(
        right[..., None],
        np.where((v < 0.4)[..., None], lin(OCHRE), np.where((v < 0.7)[..., None], lin(LEATHER), lin(SOLE))),
        lin(WOOL),
    )
    shade = 1 + np.where(right, 0.06 * mott, 0.03 * weave + 0.05 * mott - 0.10 * slub)
    rgb = np.clip(base * shade[..., None], 0, 1) ** (1 / 2.2)
    Image.fromarray((rgb * 255 + 0.5).astype(np.uint8), "RGB").save(os.path.join(out, "tunic_base.png"))

    # normal map from the height field (strength in texels)
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    k = 0.35
    n = np.stack([-gx * k, gy * k, np.ones_like(h)], -1)  # +Y up in UV (OpenGL convention, as glTF)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    Image.fromarray(((n * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8), "RGB").save(os.path.join(out, "tunic_nrm.png"))
    lean = np.degrees(np.arccos(np.clip(n[..., 2].mean(), -1, 1)))
    print(f"tunic_base.png, tunic_nrm.png ({S}), mean normal lean {lean:.1f} deg")


if __name__ == "__main__":
    main(sys.argv[1])
