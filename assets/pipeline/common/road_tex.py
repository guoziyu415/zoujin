"""Source textures for the road stops (F-10) and the village (F-11): scans when they are there, generated placeholders
otherwise.

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
pt.HI = {"road", "grass", "outcrop", "bank", "wood", "earth"}


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


# ---------------------------------------------------------------- foliage on a transparent ground (RGBA, alpha-tested)
# (UX round 2 ④: the crowns read as low-poly balls and the willow's strands as flat green sticks). Small: 512 or 256.
from PIL import Image, ImageDraw  # noqa: E402

SMALL = {"poplar": 512, "willow": 512, "holmoak": 512, "willowstrand": 256, "reed": 256, "fig": 512, "vine": 512}
_size_of = pt.size_of
pt.size_of = lambda key: SMALL.get(key) or _size_of(key)

_save = pt.save


def save(key, kind, arr):
    if arr.ndim == 3 and arr.shape[-1] == 4:
        p = pt.OUT / f"{key}_{kind}.png"
        Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(p, optimize=True)
        return p
    return _save(key, kind, arr)


pt.save = save


def leaf(d, cx, cy, length, width, ang, fill, rib=None):
    """one leaf: a pointed egg, its broad end at the stalk (cx, cy), pointing along ang"""
    pts = []
    for t in np.linspace(0, 2 * np.pi, 28, endpoint=False):
        u = (np.cos(t) + 1) * 0.5 * length
        v = np.sin(t) * width * 0.5 * (1 - 0.45 * np.cos(t)) * (1 - 0.6 * (np.cos(t) > 0.6) * (np.cos(t) - 0.6))
        pts.append((cx + u * np.cos(ang) - v * np.sin(ang), cy + u * np.sin(ang) + v * np.cos(ang)))
    d.polygon(pts, fill=fill)
    if rib:
        d.line([(cx, cy), (cx + length * 0.9 * np.cos(ang), cy + length * 0.9 * np.sin(ang))], fill=rib, width=1)


def finish(img, S, h=None):
    """down to S x S (premultiplied, so no dark fringes), and the transparent texels given the leaves' mean colour"""
    small = img.convert("RGBa").resize((S, S if h is None else h), Image.LANCZOS).resize((S, S), Image.LANCZOS)
    a = np.asarray(small.convert("RGBA"), np.float32) / 255.0
    on = a[..., 3] > 0.5
    mean = a[on][:, :3].mean(0) if on.any() else np.array([0.3, 0.35, 0.25])
    a[..., :3] = np.where(a[..., 3:] > 0.02, a[..., :3], mean)
    a[..., 3] = np.where(a[..., 3] > 0.5, 1.0, np.clip(a[..., 3] * 1.6, 0, 1))
    return a


def leaves(key, S, n, size, aspect, top, under, share, droop=None):
    """a tiling cluster of leaves (the crowns' blobs repeat it every 1.6 m, the leaf cards show a piece of it);
    each leaf drawn at the nine wrapped positions so the tile has no seam. size: leaf length as a share of the tile"""
    r = rng(key)
    K = 4
    W = S * K
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for _ in range(n):
        cx, cy = r.random() * W, r.random() * W
        L = r.uniform(0.7, 1.3) * size * W
        ang = r.uniform(0, 2 * np.pi) if droop is None else np.pi / 2 + r.normal(0, droop)
        base = np.array(under if r.random() < share else top, np.float32) * r.uniform(0.78, 1.15)
        fill = tuple(int(c) for c in np.clip(base, 0, 255)) + (255,)
        rib = tuple(int(c * 0.8) for c in fill[:3]) + (255,)
        for ox in (-W, 0, W):
            for oy in (-W, 0, W):
                leaf(d, cx + ox, cy + oy, L, L * aspect, ang, fill, rib if L > 24 else None)
    return finish(img, S)


def strands(key, S):
    """the willow's hanging twigs on a card about 0.3 m wide and 3 m long: drawn in metres (a tall canvas), squashed
    into the square; a twig down the middle with narrow leaves hanging off it"""
    r = rng(key)
    W, H = S * 2, S * 20   # 0.3 m x 3 m
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    px = W / 0.3
    for k in range(3):   # three twigs side by side, wandering a little
        x0 = W * (0.3 + 0.2 * k) + r.uniform(-0.03, 0.03) * px
        y = r.uniform(0, 0.4) * px
        pts = []
        while y < H:
            x0 += r.normal(0, 0.004) * px
            pts.append((x0, y))
            side = 1 if len(pts) % 2 else -1
            L = r.uniform(0.05, 0.09) * px
            ang = np.pi / 2 + side * r.uniform(0.25, 0.6)
            g = np.array((104, 124, 76), np.float32) * r.uniform(0.8, 1.15)
            if r.random() < 0.25:
                g = np.array((150, 162, 130), np.float32) * r.uniform(0.85, 1.1)
            leaf(d, x0, y, L, L * 0.2, ang, tuple(int(c) for c in g) + (255,))
            y += r.uniform(0.02, 0.035) * px
        d.line(pts, fill=(92, 84, 60, 255), width=max(1, int(0.004 * px)))
    return finish(img, S, h=S * 10)


def reed(key, S):
    """reed clumps on cards about 0.5 m wide and 1.3 m tall: blades from the foot, tapering, leaning, a few bent over;
    straw and grey-green (the early summer)"""
    r = rng(key)
    W, H = S * 2, int(S * 2 * 1.3 / 0.5)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for _ in range(46):
        x = W * r.uniform(0.15, 0.85)
        top = H * r.uniform(0.0, 0.35)
        lean = r.normal(0, 0.12) * W
        w = W * r.uniform(0.008, 0.016)
        g = np.array((126, 132, 86) if r.random() < 0.6 else (168, 156, 108), np.float32) * r.uniform(0.75, 1.1)
        col = tuple(int(c) for c in g) + (255,)
        bend = r.random() < 0.2
        pts_l, pts_r = [], []
        for t in np.linspace(0, 1, 12):
            yy = H - t * (H - top)
            xx = x + lean * t * t
            if bend and t > 0.6:
                xx += (t - 0.6) * W * 0.5
                yy += (t - 0.6) ** 2 * H * 0.8
            ww = w * (1 - t) + 0.5
            pts_l.append((xx - ww, yy))
            pts_r.append((xx + ww, yy))
        d.polygon(pts_l + pts_r[::-1], fill=col)
    return finish(img, S, h=H // 2)


def wheat(key, S):
    """ripe wheat on cards 0.7 m wide and 1 m tall (two cards side by side in the texture): stalks from the foot, each
    with a bearded ear, gold with a few greener ones (early summer, village.md 6.2: the harvest)"""
    r = rng(key)
    W, H = S * 2, S * 2
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for _ in range(240):
        x = W * r.uniform(0.02, 0.98)
        top = H * r.uniform(0.04, 0.32)
        lean = r.normal(0, 0.03) * W
        g = np.array((214, 178, 104) if r.random() < 0.85 else (176, 168, 96), np.float32) * r.uniform(0.75, 1.1)
        col = tuple(int(c) for c in np.clip(g, 0, 255)) + (255,)
        stalk = tuple(int(c * 0.85) for c in col[:3]) + (255,)
        tx = x + lean
        d.line([(x, H), (tx, top + H * 0.09)], fill=stalk, width=max(2, int(W * 0.004)))
        if r.random() < 0.5:   # a dry blade off the stalk
            yb = H - r.uniform(0.15, 0.5) * (H - top)
            xb = x + (tx - x) * (H - yb) / (H - top)
            leaf(d, xb, yb, H * r.uniform(0.12, 0.2), H * 0.012, -np.pi / 2 + r.choice((-1, 1)) * r.uniform(0.3, 0.7), stalk)
        ear_l = H * r.uniform(0.07, 0.1)
        ang = np.arctan2(-(H - top), lean) + r.normal(0, 0.15)
        cx, cy = tx, top + H * 0.09
        leaf(d, cx, cy, ear_l, ear_l * 0.28, ang, col)
        for k in range(6):   # the beard
            t = (k + 0.5) / 6
            px, py = cx + np.cos(ang) * ear_l * t, cy + np.sin(ang) * ear_l * t
            for s in (-1, 1):
                a2 = ang + s * 0.35
                d.line([(px, py), (px + np.cos(a2) * ear_l * 0.6, py + np.sin(a2) * ear_l * 0.6)], fill=col, width=1)
    return finish(img, S)


def village_make(key):
    """the village's own placeholders (F-11, ux/scenes/village.md 6.2); None for a key that is not one of them"""
    S = pt.size_of(key)
    r = rng(key)
    out = {}
    if key == "earth":
        # the beaten earth of a yard: pale and dusty in the sun, packed smooth, a little grit
        g = fbm(r, S, base=4)
        fine = fbm(rng(key, "f"), S, base=40, octaves=3)
        stones, st = blobs(rng(key, "s"), S, 160, 0.003, 0.008)
        h = 0.6 * g + 0.25 * fine + 0.25 * stones
        out["base"] = colour((202, 186, 154), (g - 0.5) * 1.0 + 0.3 * st * (stones > 0), fine, 0.18)
        out["nrm"] = normal_from_height(h, 3.0)
        out["mr"] = mr(np.clip(0.88 + 0.08 * fine, 0, 1))
    elif key == "stubble":
        # a reaped field: short pale-gold stalks in rows over dry brown soil
        g = fbm(r, S, base=6)
        yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) / S
        rows = 0.5 + 0.5 * np.cos((yy + 0.01 * fbm(rng(key, "w"), S, base=4)) * 2 * np.pi * 16)
        stalks = value_noise(rng(key, "b"), S, 256)
        on = (stalks > 0.55) & (rows > 0.3)
        soil = colour((150, 126, 92), (g - 0.5) * 1.2, fbm(rng(key, "f"), S, base=32, octaves=3), 0.2)
        straw = colour((212, 186, 122), (stalks - 0.5) * 2, g, 0.2)
        out["base"] = np.where(on[..., None], straw, soil)
        out["nrm"] = normal_from_height(0.5 * g + 0.5 * on * stalks, 5.0)
        out["mr"] = mr(np.clip(0.9 + 0.06 * g, 0, 1))
    elif key == "mudplaster":
        # rough stone walls under an earthy lime plaster, yellower than the town's, flaking in patches to the stone
        g = fbm(r, S, base=4)
        fine = fbm(rng(key, "f"), S, base=32, octaves=4)
        st, tone = blobs(rng(key, "s"), S, 90, 0.02, 0.05)
        c = colour((200, 176, 132), (g - 0.5) * 1.2, fine, 0.12)
        flake = (g < 0.3)[..., None]
        stone = colour((168, 156, 134), tone, fine, 0.2) * (0.75 + 0.25 * st)[..., None]
        out["base"] = np.where(flake, stone, c)
        out["nrm"] = normal_from_height(0.5 * g + 0.3 * fine + 0.4 * flake[..., 0] * st, 4.0)
        out["mr"] = mr(np.clip(0.9 + 0.06 * fine, 0, 1))
    elif key == "wheat":
        out["base"] = wheat(key, S)
    else:
        return None
    return out


LEAVES = {
    # white poplar: broad leaves, dark green above, white-felted below (the crowns flicker silver)
    "poplar": dict(n=420, size=0.07, aspect=0.75, top=(66, 90, 50), under=(176, 186, 170), share=0.3),
    # holm oak: small, leathery, very dark, a dense mass
    "holmoak": dict(n=900, size=0.04, aspect=0.5, top=(46, 60, 38), under=(92, 100, 74), share=0.15),
    # willow: narrow, light grey-green, hanging
    "willow": dict(n=700, size=0.06, aspect=0.2, top=(100, 120, 74), under=(150, 160, 128), share=0.25, droop=0.5),
    # fig (the village yard, village.md 6.2): big leaves, mid green, a lighter underside
    "fig": dict(n=260, size=0.11, aspect=0.85, top=(70, 98, 52), under=(124, 144, 92), share=0.2),
    # vine (the groom's arbour and vineyard): broad leaves, fresh early-summer green
    "vine": dict(n=300, size=0.1, aspect=0.95, top=(86, 116, 58), under=(136, 154, 98), share=0.25),
}


def make(key):
    v = village_make(key)
    if v is not None:
        return v
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
        # pale grey-white karst limestone, weathered smooth, peppered with fine dark pits and small solution holes,
        # a faint ochre stain here and there (UX round 2: the big black lichen blobs read as camouflage)
        g = fbm(r, S, base=3)
        pits = fbm(rng(key, "p"), S, base=24, octaves=4)
        fine = value_noise(rng(key, "f"), S, 320)
        holes, _ = blobs(rng(key, "h"), S, 700, 0.0015, 0.004)
        stain = fbm(rng(key, "l"), S, base=6, octaves=3)
        c = colour((196, 192, 180), (g - 0.5) * 1.0, pits, 0.12)
        c = c * (1 - 0.2 * np.clip((fine - 0.8) / 0.1, 0, 1))[..., None]   # pits: small, soft
        c = c * (1 - 0.3 * holes)[..., None]
        ochre = (np.clip((stain - 0.62) / 0.12, 0, 1) * 0.25)[..., None]
        c = c * (1 - ochre) + np.array([0.72, 0.6, 0.42]) * ochre
        out["base"] = c
        out["nrm"] = normal_from_height(g * 0.5 + pits * 0.3 - holes * 0.4 - 0.15 * fine, 7.0)
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
    elif key in LEAVES:
        out["base"] = leaves(key, S, **LEAVES[key])
    elif key == "willowstrand":
        out["base"] = strands(key, S)
    elif key == "reed":
        out["base"] = reed(key, S)
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
    "willowstrand": ["base"],
    "reed": ["base"],
    "holmoak": ["base"],
    # the village (F-11)
    "earth": ["base", "nrm", "mr"],
    "stubble": ["base", "nrm", "mr"],
    "mudplaster": ["base", "nrm", "mr"],
    "roofwarm": ["base"],
    "wheat": ["base"],
    "fig": ["base"],
    "vine": ["base"],
}

if __name__ == "__main__":
    pt.main()
