"""Source textures for the plaza: real scans when they are there, generated placeholders otherwise.

    python3 placeholder_tex.py <out_dir> [<scan_dir>]

For every texture build_plaza.py asks for (<key>_base / _nrm / _mr), take <scan_dir>/<key>_<kind>.jpg|png
when it exists (CC0 scans listed in assets/manifest/plaza-textures.json, fetched where the sites are
reachable), otherwise draw a placeholder. Placeholders are drawn from noise with fixed seeds, so they are
CC0 by construction and the same on every run. Writes <out_dir>/<key>_<kind>.png plus sources.json
saying which is which; scene.json carries that on, and the test page labels placeholder materials.

Colours follow ux/art-direction 4.2 (honey-white limestone, faded orange-brown tiles, no red except the
player's sash). Roughness is in G and metalness in B of _mr, as glTF wants.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(sys.argv[1])
SCANS = Path(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else None
OUT.mkdir(parents=True, exist_ok=True)

# the high tier swaps these to 2048 colour + 1024 normal (art-direction 9.3), so their sources are 2048
HI = {"floor", "ashlar", "ashlar2", "plaster", "plain", "doors", "roof", "roofwarm"}


def size_of(key):
    return 2048 if key in HI else 1024


def rng(key, salt=""):
    return np.random.default_rng(int(hashlib.sha256((key + salt).encode()).hexdigest()[:8], 16))


# ---------------------------------------------------------------- tileable noise
def value_noise(r, size, cells):
    """periodic value noise in [0, 1]: a random grid upsampled bicubically on a 3 x 3 tiling, centre kept"""
    g = r.random((cells, cells)).astype(np.float32)
    t = np.tile(g, (3, 3))
    im = Image.fromarray(t, "F").resize((size * 3, size * 3), Image.BICUBIC)
    a = np.asarray(im)[size : 2 * size, size : 2 * size]
    return np.clip(a, 0, 1)


def fbm(r, size, base=4, octaves=6, gain=0.5):
    a = np.zeros((size, size), np.float32)
    amp, tot, cells = 1.0, 0.0, base
    for _ in range(octaves):
        if cells > size:
            break
        a += amp * value_noise(r, size, cells)
        tot += amp
        amp *= gain
        cells *= 2
    return a / tot


def norm01(a):
    lo, hi = np.percentile(a, 1), np.percentile(a, 99)
    return np.clip((a - lo) / max(hi - lo, 1e-6), 0, 1)


# ---------------------------------------------------------------- patterns (height in [0, 1], plus a per-piece tone)
def running_bond(r, size, rows, len_min, len_max, gap, bevel, jitter=0.15):
    """rows of blocks of random length (in tile units), like flagstones or ashlar courses"""
    h = np.zeros((size, size), np.float32)
    tone = np.zeros((size, size), np.float32)
    row_h = size / rows
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    for i in range(rows):
        y0, y1 = i * row_h, (i + 1) * row_h
        x = r.random() * size
        start = x
        while x < start + size:
            ln = r.uniform(len_min, len_max) * size
            t = r.uniform(-1, 1) * jitter
            for shift in (-size, 0, size):
                x0, x1 = x + shift, x + ln + shift
                if x1 < 0 or x0 > size:
                    continue
                m = (yy >= y0) & (yy < y1) & (xx >= x0) & (xx < x1)
                if not m.any():
                    continue
                d = np.minimum.reduce([xx - x0, x1 - xx, yy - y0, y1 - yy])
                prof = np.clip((d - gap * size) / max(bevel * size, 1e-3), 0, 1)
                h[m] = np.maximum(h[m], prof[m] * (0.85 + 0.15 * r.random()))
                tone[m] = t
            x += ln
    return h, tone


def tiles_rows(r, size, cols, rows):
    """Greek pan-and-cover roof tiles: rounded cover tiles across u, overlapping courses along v"""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
    u = (xx * cols) % 1.0
    v = (yy * rows) % 1.0
    cover = np.clip(np.cos((u - 0.5) * np.pi * 2.2), 0, 1) ** 0.6
    pan = 0.35 * (1 - np.abs(np.sin(u * np.pi)))
    lap = 0.6 + 0.4 * v  # each course rises towards the one above it
    h = np.maximum(cover, pan) * lap
    tone = (value_noise(r, size, cols * 2) - 0.5) * 0.25
    return h, tone


def weave(size, threads):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
    a = np.sin(xx * threads * 2 * np.pi)
    b = np.sin(yy * threads * 2 * np.pi)
    return 0.5 + 0.25 * (a * np.sign(b) + b * np.sign(a)) * 0.5


# ---------------------------------------------------------------- output helpers
def colour(base, tone, grain, spread=0.18):
    base = np.array(base, np.float32) / 255.0
    k = 1 + spread * (tone[..., None]) + 0.22 * (grain[..., None] - 0.5)
    return np.clip(base[None, None, :] * k, 0, 1)


def normal_from_height(h, strength):
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    dy = -(np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5  # image rows go down, v goes up
    n = np.stack([-dx * strength, -dy * strength, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def save(key, kind, arr):
    a = (np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8)
    mode = "L" if a.ndim == 2 else "RGB"
    p = OUT / f"{key}_{kind}.png"
    Image.fromarray(a, mode).save(p, optimize=True)
    return p


def mr(rough):
    z = np.zeros_like(rough)
    return np.stack([np.ones_like(rough), rough, z], -1)  # R unused (occlusion slot), G rough, B metal


# ---------------------------------------------------------------- each material
def make(key):
    S = size_of(key)
    r = rng(key)
    out = {}
    if key == "floor":
        h, tone = running_bond(r, S, rows=4, len_min=0.22, len_max=0.42, gap=0.004, bevel=0.012)
        pits = fbm(rng(key, "p"), S, base=16)
        grain = fbm(rng(key, "g"), S, base=8)
        hh = h * (0.9 + 0.1 * pits)
        grout = h < 0.05
        c = colour((178, 162, 134), tone, grain)
        c[grout] = c[grout] * 0.62 + np.array([0.30, 0.26, 0.20]) * 0.38  # dust and dry grass in the joints
        out["base"] = c
        out["nrm"] = normal_from_height(hh, 6.0)
        rough = 0.72 + 0.18 * norm01(pits) + 0.1 * grout
        out["mr"] = mr(np.clip(rough, 0, 1))
    elif key in ("ashlar", "ashlar2"):
        h, tone = running_bond(r, S, rows=6, len_min=0.18, len_max=0.4, gap=0.003, bevel=0.006)
        chisel = fbm(rng(key, "c"), S, base=32, octaves=4)
        grain = fbm(rng(key, "g"), S, base=6)
        base = (198, 180, 148) if key == "ashlar" else (206, 172, 126)
        c = colour(base, tone, grain, 0.14)
        c *= (0.8 + 0.2 * h)[..., None]  # joints read darker, like the mortar line in a scan
        out["base"] = c
        if key == "ashlar":
            out["nrm"] = normal_from_height(h * (0.92 + 0.08 * chisel), 5.0)
            out["mr"] = mr(0.8 + 0.12 * chisel)
    elif key in ("plain", "plaster"):
        g = fbm(r, S, base=4)
        fine = fbm(rng(key, "f"), S, base=32, octaves=4)
        if key == "plain":
            out["base"] = colour((170, 154, 130), (g - 0.5) * 2, fine, 0.2)
            out["nrm"] = normal_from_height(g * 0.6 + fine * 0.4, 4.0)
            out["mr"] = mr(0.85 + 0.1 * fine)
        else:
            # warm white lime plaster; where the blotch noise is low it has flaked off and the stone shows
            c = colour((216, 200, 172), (g - 0.5) * 1.2, fine, 0.1)
            flake = g < 0.32
            c[flake] = c[flake] * 0.72 + np.array([0.62, 0.55, 0.45]) * 0.28
            out["base"] = c
    elif key in ("roof", "roofwarm"):
        h, tone = tiles_rows(r, S, cols=6, rows=8)
        grain = fbm(rng(key, "g"), S, base=8)
        shade = (0.62 + 0.38 * h)[..., None]  # the gaps under each cover tile are in shadow
        if key == "roofwarm":
            out["base"] = colour((168, 102, 68), tone * 4, grain, 0.2) * shade  # faded orange-brown, not the sash red
        else:
            out["base"] = colour((156, 104, 76), tone * 4, grain, 0.2) * shade
            out["nrm"] = normal_from_height(h, 8.0)
            out["mr"] = mr(0.78 + 0.15 * grain)
    elif key == "doors":
        out.update(doors_atlas(r, S))
    elif key in ("cornice", "trim"):
        yy = np.mgrid[0:S, 0:S][0].astype(np.float32) / S
        bands = 0.5 + 0.5 * np.sign(np.sin(yy * 2 * np.pi * (5 if key == "cornice" else 3)))
        mould = 0.5 + 0.5 * np.cos(yy * 2 * np.pi * (10 if key == "cornice" else 6))
        grain = fbm(r, S, base=8)
        h = 0.6 * bands + 0.4 * mould
        out["base"] = colour((192, 176, 148) if key == "cornice" else (186, 170, 142), (h - 0.5) * 0.5, grain, 0.2)
        out["nrm"] = normal_from_height(h, 10.0)
        if key == "cornice":
            out["mr"] = mr(0.82 + 0.1 * grain)
    elif key in ("fabric_red", "fabric_blue"):
        xx = np.mgrid[0:S, 0:S][1].astype(np.float32) / S
        stripe = (np.floor(xx * 8) % 2).astype(np.float32)
        w = weave(S, 160)
        grain = fbm(r, S, base=8)
        # «red» is a faded madder-ochre here: art-direction 6 keeps real red for the player's sash
        a = (176, 120, 74) if key == "fabric_red" else (98, 120, 136)
        b = np.array((212, 198, 172), np.float32) / 255.0
        c = colour(a, (w - 0.5) * 0.6, grain, 0.2)
        c[stripe > 0] = c[stripe > 0] * 0.25 + b * 0.75
        out["base"] = c
        if key == "fabric_red":
            out["nrm"] = normal_from_height(w, 3.0)
        out["mr"] = mr(0.92 + 0.05 * grain)
    elif key == "hill":
        g = fbm(r, S, base=6)
        f = fbm(rng(key, "f"), S, base=48, octaves=3)
        out["base"] = colour((152, 140, 98), (g - 0.5) * 2, f, 0.25)  # dry summer grass and scrub
    elif key == "bark":
        xx = np.mgrid[0:S, 0:S][1].astype(np.float32) / S
        streak = value_noise(r, S, 64)
        streak = np.asarray(Image.fromarray(streak, "F").resize((S, 4)).resize((S, S), Image.BICUBIC))
        out["base"] = colour((90, 74, 60), (streak - 0.5) * 2, fbm(rng(key, "g"), S, base=16), 0.3)
    elif key in ("cypress", "olive"):
        g = fbm(r, S, base=24, octaves=4)
        out["base"] = colour((40, 58, 38) if key == "cypress" else (112, 122, 98), (g - 0.5) * 3, g, 0.3)
    elif key == "ivy":
        g = fbm(r, S, base=24, octaves=4)
        out["nrm"] = normal_from_height(g, 6.0)
    else:
        raise KeyError(key)
    return out


def doors_atlas(r, S):
    """The atlas build_plaza.py maps facade openings onto (UV rects DOOR, SHUTTER, BARRED; v = 0 at the bottom):
    an arched plank door, a window with closed dark shutters, a small barred window; plaster everywhere else."""
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    u, v = xx / S, 1 - yy / S
    grain = fbm(r, S, base=16)
    plaster = colour((214, 198, 170), (fbm(rng("doors", "p"), S, base=4) - 0.5), grain, 0.1)
    h = np.full((S, S), 0.5, np.float32)
    rough = np.full((S, S), 0.88, np.float32)
    c = plaster.copy()
    wood = fbm(rng("doors", "w"), S, base=8)
    planks = (np.abs(((u * 14) % 1.0) - 0.5) > 0.46).astype(np.float32)
    wood_c = colour((112, 94, 74), (wood - 0.5), wood, 0.25)  # sun-greyed old wood (art-direction 4.2)

    def rect(u0, v0, u1, v1):
        return (u >= u0) & (u < u1) & (v >= v0) & (v < v1)

    # door: (0.0, 0.012, 0.49, 0.94), arch on top
    u0, v0, u1, v1 = 0.0, 0.012, 0.49, 0.94
    cx, w = (u0 + u1) / 2, (u1 - u0) / 2
    arch_v = v1 - w * 0.9
    inside = rect(u0 + 0.04, v0, u1 - 0.04, v1) & ((v < arch_v) | (((u - cx) / (w - 0.04)) ** 2 + ((v - arch_v) / (w * 0.9)) ** 2 < 1))
    frame = rect(u0, v0, u1, v1) & ~inside & ((v < arch_v) | (((u - cx) / w) ** 2 + ((v - arch_v) / (w * 0.9)) ** 2 < 1))
    c[frame] = colour((188, 172, 144), np.zeros((S, S)), grain, 0.1)[frame]
    h[frame] = 0.75
    c[inside] = wood_c[inside] * (1 - 0.35 * planks[inside, None])
    h[inside] = 0.3 + 0.1 * wood[inside] - 0.15 * planks[inside]
    rough[inside] = 0.8
    # shutters: (0.50, 0.425, 0.905, 1.0)
    s = rect(0.53, 0.45, 0.875, 0.97)
    slats = (np.abs(((v * 60) % 1.0) - 0.5) > 0.4).astype(np.float32)
    split = np.abs(u - 0.7025) < 0.004
    dark = colour((70, 60, 50), np.zeros((S, S)), wood, 0.25)
    c[s] = dark[s] * (1 - 0.3 * slats[s, None])
    c[s & split] *= 0.5
    h[s] = 0.35 - 0.1 * slats[s]
    c[rect(0.50, 0.425, 0.905, 1.0) & ~s] = colour((188, 172, 144), np.zeros((S, S)), grain, 0.1)[rect(0.50, 0.425, 0.905, 1.0) & ~s]
    # barred window: (0.50, 0.0, 0.86, 0.41)
    b = rect(0.54, 0.05, 0.82, 0.37)
    bars = (np.abs(((u - 0.54) / 0.28 * 5) % 1.0 - 0.5) < 0.08) & b
    c[b] = np.array([0.08, 0.07, 0.06])
    c[bars] = np.array([0.22, 0.2, 0.18])
    h[b] = 0.1
    h[bars] = 0.4
    return {"base": c, "nrm": normal_from_height(h, 6.0), "mr": mr(rough)}


NEEDS = {
    "floor": ["base", "nrm", "mr"],
    "ashlar": ["base", "nrm", "mr"],
    "ashlar2": ["base"],
    "plain": ["base", "nrm", "mr"],
    "plaster": ["base"],
    "roof": ["nrm", "mr"],
    "roofwarm": ["base"],
    "doors": ["base", "nrm", "mr"],
    "cornice": ["base", "nrm", "mr"],
    "trim": ["base", "nrm"],
    "fabric_red": ["base", "nrm", "mr"],
    "fabric_blue": ["base", "mr"],
    "hill": ["base"],
    "bark": ["base"],
    "cypress": ["base"],
    "olive": ["base"],
    "ivy": ["nrm"],
}


def main():
    sources = {}
    for key, kinds in NEEDS.items():
        made = None
        for kind in kinds:
            src = None
            if SCANS:
                for ext in (".png", ".jpg"):
                    p = SCANS / f"{key}_{kind}{ext}"
                    if p.exists():
                        src = p
                        break
            dst = OUT / f"{key}_{kind}.png"
            if src:
                if src.suffix == ".png":
                    shutil.copyfile(src, dst)
                else:
                    Image.open(src).save(dst, optimize=True)
                sources[f"{key}_{kind}"] = {"from": "scan", "file": src.name}
            else:
                made = made or make(key)
                save(key, kind, made[kind])
                sources[f"{key}_{kind}"] = {"from": "placeholder"}
            sources[f"{key}_{kind}"]["sha256"] = hashlib.sha256(dst.read_bytes()).hexdigest()
            print(key, kind, sources[f"{key}_{kind}"]["from"], flush=True)
    (OUT / "sources.json").write_text(json.dumps(sources, indent=1) + "\n")


if __name__ == "__main__":
    main()
