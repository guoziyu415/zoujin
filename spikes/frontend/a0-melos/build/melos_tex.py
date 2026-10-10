"""Melos's clothes texture: one 1024 colour map and one normal map for the `Tunic` object (A-0 step 2).

python3 melos_tex.py <out_dir>   ->  tunic_base.png (sRGB), tunic_nrm.png (tangent space, OpenGL +Y)

UV regions as melos_clothes_v2.NEW_UV (u0, u1, v0, v1): the tunic's wool on the left (u 0..0.62); on the right the
bundle, the bands that tie it, the rope, the sandal straps and the soles, top to bottom in the image. Colours from
the style guide (docs/ux/style-guide/characters/melos.md, palette in art-direction 5.4): tunic ochre O1 #A5733F,
washed out in patches; bundle, bands and rope undyed wool W0 #CBBDA3 (the bands and rope darker with handling);
sandals old leather K1 #6E4A2E, soles darker.
Dust on the hem and the sandals, and sun fade on the shoulders, depend on where a texel sits on the body, so
melos_prep.py paints them from the geometry. Generated from a fixed seed, no downloads: the output is reproducible.
"""

import os
import sys

import numpy as np
from PIL import Image

S = 1024
O1 = (165, 115, 63)
W0 = (203, 189, 163)
K1 = (110, 74, 46)
SOLE = (78, 52, 33)
# keep in step with melos_clothes_v2.NEW_UV (that module needs bpy, so it is not imported here)
NEW_UV = {
    "wool": (0.0, 0.62, 0.0, 1.0),
    "bundle": (0.62, 1.0, 0.0, 0.45),
    "bands": (0.62, 1.0, 0.45, 0.6),
    "rope": (0.62, 1.0, 0.6, 0.7),
    "straps": (0.62, 1.0, 0.7, 0.85),
    "soles": (0.62, 1.0, 0.85, 1.0),
}


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
    u, v = (xx + 0.5) / S, 1.0 - (yy + 0.5) / S  # image row 0 is v = 1

    def region(name):
        u0, u1, v0, v1 = NEW_UV[name]
        inside = (u >= u0) & (u < u1) & (v >= v0) & (v < v1)
        return inside, (u - u0) / (u1 - u0), (v - v0) / (v1 - v0)

    weave = np.sin(xx * 2 * np.pi / 3) * np.sin(yy * 2 * np.pi / 3)  # plain weave, ~1.5 mm threads
    slub = np.clip(noise(rng, 4, 1) - 1.6, 0, None)
    mott = noise(rng, 32, 9)
    folds = noise(rng, 96, 30)
    fade = 0.5 + 0.5 * np.tanh(noise(rng, 128, 40) * 1.2)  # washed-out patches, soft-edged
    grain = noise(rng, 6, 2)
    broad = noise(rng, 64, 16)

    h = np.zeros((S, S), np.float32)
    base = np.zeros((S, S, 3), np.float32)
    shade = np.ones((S, S), np.float32)

    # tunic: ochre wool, washed out all over and more in patches, towards a paler, greyer ochre
    m, _, _ = region("wool")
    paler = lin(O1) * 0.6 + lin((196, 182, 155)) * 0.4
    wash = 0.1 + 0.4 * fade[m, None]
    base[m] = lin(O1)[None] * (1 - wash) + paler[None] * wash
    h[m] = (0.35 * weave + 0.8 * slub + 2.5 * folds)[m]
    shade[m] = (1 + 0.03 * weave + 0.05 * mott - 0.10 * slub)[m]

    # bundle: undyed wool cloth gathered towards its top (the knot): creases run from the top pole downwards
    m, bu, bv = region("bundle")
    lines = np.zeros((S, S), np.float32)
    for c, w, d in zip(rng.uniform(0, 1, 26), rng.uniform(0.004, 0.012, 26), rng.uniform(0.4, 1.0, 26)):
        wob = 0.012 * np.sin(bv * 7 + 40 * c)
        lines += d * np.exp(-(((bu - c - wob + 0.5) % 1 - 0.5) ** 2) / (2 * w * w))
    top = np.clip((bv - 0.45) / 0.55, 0, 1) ** 1.5 + 0.35 * np.clip((0.25 - bv) / 0.25, 0, 1)
    crease = lines * top
    base[m] = lin(W0) * (0.9 + 0.06 * mott[m, None])  # carried all day: a little grubby
    h[m] = (0.35 * weave + 0.6 * slub + 1.5 * folds - 3.0 * crease)[m]
    shade[m] = (1 + 0.03 * weave + 0.05 * mott - 0.08 * slub - 0.22 * np.clip(crease, 0, 1))[m]

    # bands: corners of the same cloth twisted into strips; creases along their length (u)
    m, _, cv = region("bands")
    along = np.sin(cv * 2 * np.pi * 2 + 1.5 * folds + 0.8 * np.sin(xx / 23)) * 0.5 + 0.5
    base[m] = lin(W0) * 0.8  # handled and sweated on
    h[m] = (0.3 * weave + 1.2 * along)[m]
    shade[m] = (1 + 0.03 * weave + 0.05 * mott - 0.15 * (1 - along))[m]

    # rope: two-ply twist, about 1 cm a turn; the grooves dark
    m, ru, rv = region("rope")
    twist = np.sin(np.pi * (ru * 85 + 2 * rv))  # |twist|: 85 strand crossings along the waist loop, ~1 cm each
    base[m] = lin(W0) * 0.75
    h[m] = (1.6 * np.abs(twist) + 0.2 * grain)[m]
    shade[m] = (0.72 + 0.32 * np.abs(twist) + 0.04 * mott)[m]

    # sandals: worn leather, the soles darker
    for name, col in (("straps", K1), ("soles", SOLE)):
        m, _, _ = region(name)
        base[m] = lin(col)
        h[m] = (0.6 * grain + 1.5 * broad)[m]
        shade[m] = (1 + 0.06 * mott)[m]

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
