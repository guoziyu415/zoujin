"""Source textures for the road stops (F-10): scans when they are there, generated placeholders otherwise.

    python3 -I road_tex.py <out_dir> [<scan_dir>]

Same rules as the plaza (../plaza/placeholder_tex.py, whose helpers and main() this reuses): <scan_dir>/<key>_<kind>
wins when it exists, otherwise a placeholder drawn from fixed seeds. Colours follow ux/scenes/homeward-road.md 0.4
and 1.6 (chalky limestone road, early-summer grass mostly gone yellow, grey-white karst rock, sun-greyed wood); no red.
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("placeholder_tex", HERE.parent / "plaza" / "placeholder_tex.py")
pt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pt)  # reads <out_dir> and <scan_dir> from sys.argv like the plaza does

fbm, colour, normal_from_height, mr, rng, norm01, value_noise = (
    pt.fbm, pt.colour, pt.normal_from_height, pt.mr, pt.rng, pt.norm01, pt.value_noise)

# the high tier (homeward-road.md 9): the shared road, grass and rock, the river's wet bank and the broken piles
pt.HI = {"road", "grass", "outcrop", "bank", "wood"}


def blobs(r, S, n, rmin, rmax):
    """height of n round stones (pebbles, gravel), tiling; each stone touches only its own box"""
    h = np.zeros((S, S), np.float32)
    tone = np.zeros((S, S), np.float32)
    for _ in range(n):
        cx, cy, rr = r.random() * S, r.random() * S, r.uniform(rmin, rmax) * S
        ax = r.uniform(0.6, 1.0)
        t = r.uniform(-1, 1)
        x0, x1 = int(np.floor(cx - rr)), int(np.ceil(cx + rr)) + 1
        y0, y1 = int(np.floor(cy - rr * ax)), int(np.ceil(cy + rr * ax)) + 1
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        d = ((xx - cx) / rr) ** 2 + ((yy - cy) / (rr * ax)) ** 2
        hv = np.sqrt(np.clip(1 - d, 0, 1))
        iy, ix = np.ix_(np.arange(y0, y1) % S, np.arange(x0, x1) % S)
        cur = h[iy, ix]
        upd = (d < 1) & (hv > cur)
        cur[upd] = hv[upd]
        h[iy, ix] = cur
        tc = tone[iy, ix]
        tc[upd] = t
        tone[iy, ix] = tc
    return h, tone


def make(key):
    S = pt.size_of(key)
    r = rng(key)
    out = {}
    if key == "road":
        # pale ochre-white dust over packed limestone grit, wheel ruts along u, small stones
        g = fbm(r, S, base=4)
        fine = fbm(rng(key, "f"), S, base=48, octaves=3)
        yy = np.mgrid[0:S, 0:S][0].astype(np.float32) / S
        rut = np.exp(-(((yy % 0.5) - 0.17) / 0.03) ** 2) + np.exp(-(((yy % 0.5) - 0.33) / 0.03) ** 2)
        stones, st = blobs(rng(key, "s"), S, 260, 0.004, 0.012)
        h = 0.5 * g + 0.25 * fine - 0.25 * rut * (0.6 + 0.4 * g) + 0.35 * stones
        c = colour((196, 180, 148), (g - 0.5) * 1.2 + 0.4 * st * (stones > 0), fine, 0.2)
        c *= (1 - 0.12 * rut)[..., None]
        out["base"] = c
        out["nrm"] = normal_from_height(h, 5.0)
        out["mr"] = mr(np.clip(0.86 + 0.1 * fine - 0.08 * stones, 0, 1))
    elif key == "grass":
        # straw-yellow early-summer grass with green kept in the hollows (homeward-road.md 0.4)
        g = fbm(r, S, base=6)
        blades = value_noise(rng(key, "b"), S, 256)
        streak = np.asarray(pt.Image.fromarray(blades, "F").resize((S, S // 8)).resize((S, S), pt.Image.BICUBIC))
        green = np.clip((0.42 - g) * 4, 0, 1)
        dry = colour((176, 156, 96), (streak - 0.5) * 2, g, 0.3)
        wet = colour((104, 116, 64), (streak - 0.5) * 2, g, 0.3)
        out["base"] = dry * (1 - green[..., None]) + wet * green[..., None]
        out["nrm"] = normal_from_height(streak * 0.7 + g * 0.3, 4.0)
        out["mr"] = mr(np.clip(0.9 + 0.08 * streak, 0, 1))
    elif key == "outcrop":
        # grey-white rounded karst with black and orange lichen
        g = fbm(r, S, base=3)
        pits = fbm(rng(key, "p"), S, base=24, octaves=4)
        lich = fbm(rng(key, "l"), S, base=12, octaves=4)
        c = colour((184, 180, 168), (g - 0.5) * 1.4, pits, 0.2)
        black = np.clip((lich - 0.64) / 0.1, 0, 1)[..., None] * 0.4   # soft-edged, never more than 40% darker
        orange = (np.clip((0.26 - lich) / 0.08, 0, 1) * (pits > 0.5))[..., None] * 0.3
        c = c * (1 - black)
        c = c * (1 - orange) + np.array([0.62, 0.42, 0.16]) * orange
        out["base"] = c
        out["nrm"] = normal_from_height(g * 0.6 + pits * 0.4, 7.0)
        out["mr"] = mr(np.clip(0.82 + 0.12 * pits, 0, 1))
    elif key == "gravel":
        h, tone = blobs(r, S, 1400, 0.006, 0.02)
        c = colour((176, 168, 150), tone * 0.6, fbm(rng(key, "g"), S, base=16), 0.3)
        c *= (0.78 + 0.22 * h)[..., None]
        out["base"] = c
        out["nrm"] = normal_from_height(h, 6.0)
        out["mr"] = mr(np.clip(0.8 + 0.1 * (1 - h), 0, 1))
    elif key == "pebbles":
        # round river pebbles, cooler and a little darker than the road stones
        h, tone = blobs(r, S, 420, 0.012, 0.04)
        c = colour((150, 146, 136), tone * 1.5, fbm(rng(key, "g"), S, base=8), 0.25)
        c *= (0.5 + 0.5 * h)[..., None]
        out["base"] = c
        out["nrm"] = normal_from_height(h, 8.0)
        out["mr"] = mr(np.clip(0.75 + 0.15 * (1 - h), 0, 1))
    elif key == "bank":
        # the river bank below the grass line: damp dark limestone, mud and rounded stones
        g = fbm(r, S, base=4)
        st, tone = blobs(rng(key, "s"), S, 160, 0.01, 0.035)
        mud = colour((112, 100, 80), (g - 0.5), fbm(rng(key, "f"), S, base=32, octaves=3), 0.2)
        rock = colour((128, 126, 118), tone, g, 0.2)
        m = (st > 0.15)[..., None]
        out["base"] = np.where(m, rock * (0.7 + 0.3 * st[..., None]), mud)
        out["nrm"] = normal_from_height(0.6 * st + 0.4 * g, 6.0)
        out["mr"] = mr(np.clip(0.6 + 0.25 * g - 0.2 * st, 0, 1))
    elif key == "wood":
        # sun-greyed old wood with lengthwise grain (bridge, piles, jetty, boats)
        xx = np.mgrid[0:S, 0:S][1].astype(np.float32) / S
        grain = value_noise(r, S, 96)
        grain = np.asarray(pt.Image.fromarray(grain, "F").resize((S, 6)).resize((S, S), pt.Image.BICUBIC))
        g = fbm(rng(key, "g"), S, base=8)
        boards = (np.abs(((xx * 4) % 1.0) - 0.5) > 0.485).astype(np.float32)
        c = colour((128, 122, 110), (grain - 0.5) * 2, g, 0.25) * (1 - 0.35 * boards)[..., None]
        out["base"] = c
        out["nrm"] = normal_from_height(grain * 0.8 - 0.4 * boards, 5.0)
        out["mr"] = mr(np.clip(0.85 + 0.1 * grain, 0, 1))
    elif key == "thatch":
        grain = value_noise(r, S, 128)
        grain = np.asarray(pt.Image.fromarray(grain, "F").resize((S, 8)).resize((S, S), pt.Image.BICUBIC))
        out["base"] = colour((140, 120, 82), (grain - 0.5) * 2, fbm(rng(key, "g"), S, base=8), 0.3)
    elif key == "silt":
        g = fbm(r, S, base=6)
        out["base"] = colour((132, 108, 70), (g - 0.5), fbm(rng(key, "f"), S, base=32, octaves=3), 0.15)
    elif key in ("poplar", "willow", "reed", "holmoak"):
        g = fbm(r, S, base=24, octaves=4)
        base = {"poplar": (82, 104, 62), "willow": (104, 120, 84), "reed": (122, 128, 82), "holmoak": (52, 66, 44)}[key]
        out["base"] = colour(base, (g - 0.5) * 3, g, 0.3)
    else:
        return pt_make(key)  # bark, hill: the plaza's
    return out


pt_make = pt.make
pt.make = make
pt.NEEDS = {
    "road": ["base", "nrm", "mr"],
    "grass": ["base", "nrm", "mr"],
    "outcrop": ["base", "nrm", "mr"],
    "gravel": ["base"],   # the verges: colour only, the road's relief is enough at that size
    "pebbles": ["base", "nrm", "mr"],
    "bank": ["base", "nrm", "mr"],
    "wood": ["base", "nrm", "mr"],
    "thatch": ["base"],
    "silt": ["base"],
    "bark": ["base"],
    "hill": ["base"],
    "poplar": ["base"],
    "willow": ["base"],
    "reed": ["base"],
    "holmoak": ["base"],
}

if __name__ == "__main__":
    pt.main()
