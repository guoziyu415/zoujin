"""Source textures for the road's other stops and the run segments (F-15): everything ../common/road_tex.py draws (the
roadside keys shared through road-common come out byte for byte the same), plus this file's own.

    python3 -I rest_tex.py <out_dir> [<scan_dir>]

Kept out of ../common/road_tex.py so the river's and the village's recorded inputs stay as they are.
"""

import importlib.util
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("road_tex", HERE.parent / "common" / "road_tex.py")
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)  # not as __main__: patches the plaza's helpers, draws nothing yet
pt = rt.pt
Image, ImageDraw, leaf, finish, leaves = rt.Image, rt.ImageDraw, rt.leaf, rt.finish, rt.leaves
fbm, colour, rng = rt.fbm, rt.colour, rt.rng

# foliage and small surfaces drawn at their own size (small_tex.mjs re-encodes them so)
rt.SMALL.update({"plane": 512, "palm": 256, "fern": 256, "cypress": 256, "planebark": 512, "wetrock": 512,
                 "lushgrass": 512, "cloth": 256})


def fronds(key, S):
    """a dwarf fan palm's frond on a card: narrow segments fanning out from the stalk at the card's foot"""
    r = rng(key)
    W = S * 4
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = W / 2, W * 0.98
    for k in range(17):
        ang = -np.pi / 2 + (k - 8) * 0.085 + r.normal(0, 0.02)
        L = W * r.uniform(0.82, 0.95)
        g = np.array((92, 112, 70), np.float32) * r.uniform(0.8, 1.15)
        leaf(d, cx, cy, L, W * 0.05, ang, tuple(int(c) for c in g) + (255,))
    return finish(img, S)


def make(key):
    S = pt.size_of(key)
    r = rng(key)
    if key == "plane":
        # oriental plane (the spring): big, light green, thin (lit through from behind at 16:30)
        return {"base": leaves(key, S, n=260, size=0.1, aspect=0.95, top=(108, 134, 66), under=(150, 168, 104), share=0.35)}
    if key == "palm":
        return {"base": fronds(key, S)}
    if key == "fern":
        return {"base": leaves(key, S, n=500, size=0.05, aspect=0.9, top=(70, 104, 52), under=(96, 128, 70), share=0.3)}
    if key == "cypress":
        return {"base": leaves(key, S, n=1200, size=0.03, aspect=0.4, top=(36, 52, 34), under=(56, 70, 46), share=0.2)}
    if key == "planebark":
        # the plane's flaking bark: patches of grey, cream and grey-green
        g = fbm(r, S, base=5)
        patch = fbm(rng(key, "p"), S, base=10, octaves=2)
        a = colour((150, 146, 128), (g - 0.5), g, 0.2)
        b = colour((206, 198, 170), (g - 0.5), g, 0.2)
        c = colour((128, 136, 108), (g - 0.5), g, 0.2)
        return {"base": np.where((patch > 0.55)[..., None], b, np.where((patch < 0.38)[..., None], c, a))}
    if key == "wetrock":
        # the spring's wet limestone: darker, moss in the hollows
        g = fbm(r, S, base=4)
        moss = np.clip((fbm(rng(key, "m"), S, base=8) - 0.5) * 3, 0, 1)[..., None]
        return {"base": colour((118, 116, 106), (g - 0.5), g, 0.2) * (1 - moss)
                + colour((70, 92, 48), (g - 0.5), g, 0.3) * moss}
    if key == "lushgrass":
        g = fbm(r, S, base=6)
        return {"base": colour((98, 124, 60), (g - 0.5) * 1.5, fbm(rng(key, "f"), S, base=48, octaves=3), 0.3)}
    if key == "cloth":
        # undyed linen with ochre and indigo stripes, no red (homeward-road.md 4.4)
        yy = np.mgrid[0:S, 0:S][0].astype(np.float32) / S
        c = colour((206, 194, 166), np.zeros((S, S), np.float32), fbm(r, S, base=32, octaves=3), 0.1)
        ochre = (np.abs((yy * 6) % 1 - 0.5) < 0.05)[..., None]
        indigo = (np.abs((yy * 6 + 0.25) % 1 - 0.5) < 0.03)[..., None]
        return {"base": np.where(ochre, np.array([0.66, 0.5, 0.26]), np.where(indigo, np.array([0.2, 0.24, 0.38]), c))}
    return road_make(key)


road_make = pt.make
pt.make = make
pt.NEEDS = {**pt.NEEDS, **{k: ["base"] for k in
                           ("plane", "planebark", "palm", "fern", "cypress", "wetrock", "lushgrass", "cloth")}}

if __name__ == "__main__":
    pt.main()
