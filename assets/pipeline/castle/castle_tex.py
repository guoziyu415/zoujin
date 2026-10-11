"""Source textures for the castle (F-14): scans when they are there, generated placeholders otherwise.

    python3 -I castle_tex.py <out_dir> [<scan_dir>]

Same rules as the plaza (../plaza/placeholder_tex.py, whose helpers and main() this reuses): <scan_dir>/<key>_<kind>
wins when it exists, otherwise a placeholder drawn from fixed seeds. The courtyard's flagstones, limestone, plaster,
roof tiles and the far hills are the plaza's keys; the throne hall's own follow ux/scenes/castle.md 3 and 6.2:
polished dark stone, deep indigo wool (never read as red, art-direction 6), carved wood, dark bronze, an ochre-black
dado.
"""

import importlib.util
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("placeholder_tex", HERE.parent / "plaza" / "placeholder_tex.py")
pt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pt)  # reads <out_dir> and <scan_dir> from sys.argv like the plaza does

fbm, colour, normal_from_height, mr, rng, norm01, value_noise = (
    pt.fbm, pt.colour, pt.normal_from_height, pt.mr, pt.rng, pt.norm01, pt.value_noise)

# the high tier (castle.md 6.2): the polished floor, the plastered columns and walls, the curtains, the throne
pt.HI = {"hallfloor", "hallaxis", "plaster", "curtain", "throne"}


def make(key):
    S = pt.size_of(key)
    r = rng(key)
    out = {}
    if key == "hallfloor":
        # large polished slabs of dark grey-green stone, fine pale veins, tight joints; low roughness so the lamps
        # leave long highlights on it
        h, tone = pt.running_bond(r, S, rows=2, len_min=0.4, len_max=0.6, gap=0.002, bevel=0.004)
        vein = fbm(rng(key, "v"), S, base=6, octaves=6)
        vein = np.exp(-((vein - 0.5) / 0.012) ** 2)
        grain = fbm(rng(key, "g"), S, base=24, octaves=4)
        c = colour((58, 60, 56), tone * 0.6, grain, 0.12)
        c = c * (1 - 0.35 * vein[..., None]) + np.array([0.52, 0.5, 0.46]) * 0.35 * vein[..., None]
        joint = h < 0.05
        c[joint] *= 0.55
        out["base"] = c
        out["nrm"] = normal_from_height(h, 3.0)
        out["mr"] = mr(np.clip(0.22 + 0.12 * grain + 0.5 * joint, 0, 1))
    elif key == "hallaxis":
        # the same stone a shade paler, for the band on the axis from the door to the steps (castle.md 3.1)
        base = make("hallfloor")["base"]
        out["base"] = np.clip(base * 1.45 + 0.03, 0, 1)
    elif key == "curtain":
        # heavy wool, deep indigo (about #2B3550, castle.md 3.1), vertical pile and a faint woven band near the hem
        xx = np.mgrid[0:S, 0:S][1].astype(np.float32) / S
        yy = np.mgrid[0:S, 0:S][0].astype(np.float32) / S
        w = pt.weave(S, 220)
        streak = np.asarray(
            pt.Image.fromarray(value_noise(r, S, 96), "F").resize((S, 6)).resize((S, S), pt.Image.BICUBIC))
        c = colour((43, 53, 80), (streak - 0.5) * 1.4 + (w - 0.5) * 0.4, w, 0.25)
        band = (np.abs(yy - 0.9) < 0.02).astype(np.float32)
        c = c * (1 - 0.4 * band[..., None]) + np.array([0.2, 0.19, 0.3]) * 0.4 * band[..., None]
        out["base"] = c
        out["nrm"] = normal_from_height(w * 0.5 + streak * 0.5, 2.5)
        out["mr"] = mr(0.95 - 0.03 * w + 0 * xx)
    elif key == "throne":
        # dark carved wood: long grain, a carved lattice of shallow grooves
        streak = np.asarray(
            pt.Image.fromarray(value_noise(r, S, 128), "F").resize((S, 8)).resize((S, S), pt.Image.BICUBIC))
        yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) / S
        lattice = 0.5 + 0.5 * np.cos(xx * 2 * np.pi * 6) * np.cos(yy * 2 * np.pi * 6)
        carve = np.clip((lattice - 0.75) * 4, 0, 1)
        c = colour((84, 56, 38), (streak - 0.5) * 2, fbm(rng(key, "g"), S, base=16), 0.3)
        c *= (1 - 0.45 * carve)[..., None]
        out["base"] = c
        out["nrm"] = normal_from_height(streak * 0.3 - carve, 6.0)
        out["mr"] = mr(0.55 + 0.2 * carve)
    elif key == "bronze":
        g = fbm(r, S, base=8)
        patina = np.clip((fbm(rng(key, "p"), S, base=4) - 0.55) * 4, 0, 1)
        c = colour((96, 70, 40), (g - 0.5) * 1.5, g, 0.2)
        c = c * (1 - 0.5 * patina[..., None]) + np.array([0.2, 0.26, 0.2]) * 0.5 * patina[..., None]
        out["base"] = c
        rough = 0.42 + 0.3 * patina
        z = np.zeros_like(rough)
        out["mr"] = np.stack([np.ones_like(rough), rough, 0.85 - 0.6 * patina + z], -1)
    elif key == "dado":
        # the dark ochre-black band at the foot of the walls (castle.md 3), a little worn
        g = fbm(r, S, base=6)
        out["base"] = colour((48, 34, 24), (g - 0.5) * 1.2, fbm(rng(key, "f"), S, base=32, octaves=4), 0.2)
    else:
        return pt_make(key)  # floor, ashlar, plaster, roofwarm, hill: the plaza's
    return out


pt_make = pt.make
pt.make = make
pt.NEEDS = {
    "floor": ["base", "nrm", "mr"],
    "ashlar": ["base", "nrm", "mr"],
    "plaster": ["base"],
    "plain": ["base", "nrm", "mr"],
    "roofwarm": ["base"],
    "hill": ["base"],
    "cypress": ["base"],
    "hallfloor": ["base", "nrm", "mr"],
    "hallaxis": ["base"],
    "curtain": ["base", "nrm", "mr"],
    "throne": ["base", "nrm", "mr"],
    "bronze": ["base", "mr"],
    "dado": ["base"],
}

if __name__ == "__main__":
    pt.main()
