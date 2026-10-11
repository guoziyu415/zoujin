"""A-0 v5: Melos's tunic per UX's round 5 (ux/reviews/a0-melos.md, round 5, items 2 and 4).

Runs on the output of melos_clothes_v4.py (bpy in the container): <python> melos_clothes_v5.py -- <v4.blend> <out.blend>

- waist: under the rope ran a dark band about 4 cm tall that read as a leather belt, at every hour. Mostly v4's
  layers behind the rope: 3 mm inside the skirt in the rest pose, so in the talk and idle poses they came out
  through it, and hidden at bake time their AO is nearly black. They now lie INNER_GAP off the skin. At noon the rope
  and the bloused ring also threw a long shadow: the rope stood 1.2 cm proud of the skirt below it (with the sun at
  72 degrees a 1.2 cm step throws 3.7 cm down a wall). Cloth cinched by a rope puffs out under it as well as over it,
  so the rope sits in a groove: the skirt now comes out under the rope to just inside the rope's outer side, easing
  back over CINCH_H; the ring above is pulled in wherever its noon shadow would fall more than NOON_SHADOW past the
  rope onto that. Kept clear of the rope's knot and ends;
- bundle knot: its two ends stuck up 6-7 cm out of the knot and showed over his left shoulder like a small bird in
  every talk shot. Now 3-3.5 cm, flat on the bundle, pointing out to the sides and a little down, inside its outline;
  the knot itself pressed to half its height.

Frame: MPFB, metres, +Z up, the character faces -Y, his left is +X.
"""

import math
import os
import sys

import bpy  # first: bpy as a module brings bmesh and mathutils with it
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import melos_clothes_v2 as v2  # noqa: E402
import melos_clothes_v3 as v3  # noqa: E402

NEW_UV = v2.NEW_UV
CINCH_H = 0.045  # how far under the rope the skirt eases back to where it hung (m)
CINCH_IN = 0.002  # the skirt under the rope stays this far inside the rope's outer side
NOON_SUN = math.radians(72)  # the test page's noon (37 N, declination 19 degrees)
NOON_SHADOW = 0.01  # at most this much shadow below the rope at noon
BLOUSE_TOP = 0.10  # the ring above the rope that may be pulled in
INNER_GAP = 0.0015  # the layers behind the rope this close to the skin
CLEAR = (0.006, 0.016)  # no push this close to the rope's knot and ends (or the bands), all of it this far
EAR_LEN = (0.035, 0.03)
EAR_W = 0.013
INNER_ATTR = "__inner"  # face attribute: the layers behind the rope (melos_prep.py leaves their AO out)
PUFF_N = "__puff_n"  # vertex attribute: the puffed skirt's normals, set as custom normals at the end
KNOT_FLAT = 0.5  # the bundle's knot keeps this much of its height off the bundle


def _region(f, uvl):
    u = sum(lp[uvl].uv.x for lp in f.loops) / len(f.loops)
    v = sum(lp[uvl].uv.y for lp in f.loops) / len(f.loops)
    for name, (u0, u1, v0, v1) in NEW_UV.items():
        if u0 <= u < u1 and v0 <= v < v1:
            return name
    return None


def _azimuth(p):
    return math.atan2(p.x, -(p.y - v2.AXIS_Y))


def _inner_verts(bm, uvl, skin, lo, hi):
    """Wool vertices with more wool straight out from the skin in front of them within 4 cm: v4's layers behind the
    rope (the edges they share with the outside have the rope in front, not wool)."""
    tree = BVHTree.FromBMesh(bm)
    faces = list(bm.faces)
    wool = {v for f in faces if _region(f, uvl) == "wool" for v in f.verts}
    out = set()
    for v in wool:
        if not lo < v.co.z < hi:
            continue
        p = skin.find_nearest(v.co)[0]
        if p is None:
            continue
        d = Vector((v.co.x - p.x, v.co.y - p.y, 0.0))
        if d.length < 1e-6:
            continue
        d.normalize()
        hit = tree.ray_cast(v.co + d * 0.0008, d, 0.04)
        if hit[0] is not None and _region(faces[hit[2]], uvl) == "wool":
            out.add(v)
    return out


def waist(bm, uvl, body):
    """Puff the skirt out under the rope and keep the ring above from throwing a long shadow at noon.

    Everything in the waist's own radial frame (round the body's vertical axis), as functions of height and azimuth,
    so neighbouring vertices move alike: the skirt under the rope by A(azimuth) * a raised cosine of the depth, A
    what takes its top out to just inside the rope's outer side; the ring above clamped to the surface whose shadow
    at noon ends NOON_SHADOW below the rope."""
    rope_z = v2.ROPE_Z
    # first: a new layer drops every vertex reference taken before it
    puff_n = bm.verts.layers.float_vector.get(PUFF_N) or bm.verts.layers.float_vector.new(PUFF_N)
    skin = v2._torso_bvh(body)
    lo, hi = rope_z - CINCH_H - 0.012, rope_z + BLOUSE_TOP
    inner = _inner_verts(bm, uvl, skin, lo, hi)
    # the skirt has a ring every 2-4 cm here: two more between those under the rope, for a round puff
    cut = [e for e in bm.edges if not any(v in inner for v in e.verts)
           and all(lo < v.co.z < rope_z for v in e.verts)
           and abs(e.verts[0].co.z - e.verts[1].co.z) > 2 * (e.verts[0].co.xy - e.verts[1].co.xy).length
           and e.link_faces and all(_region(f, uvl) == "wool" for f in e.link_faces)]
    bmesh.ops.subdivide_edges(bm, edges=cut, cuts=2, use_grid_fill=True)
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    inner = _inner_verts(bm, uvl, skin, lo, hi)
    wool = {v for f in bm.faces if _region(f, uvl) == "wool" for v in f.verts}
    moving = wool - inner
    # the layers behind the rope (v4) lie close on the skin: in the talk and idle poses they came out through the
    # skirt as a band of dark cloth (hidden in the rest pose, they bake almost black in the AO), the "belt"
    hugged = 0
    for v in inner:
        p = skin.find_nearest(v.co)[0]
        if p is None:
            continue
        off = v.co - p
        if off.length > INNER_GAP:
            v.co = p + off.normalized() * INNER_GAP
            hugged += 1
    BINS = 72

    def radial(co):
        d = Vector((co.x, co.y - v2.AXIS_Y, 0.0))
        return d.length, d.normalized()

    def az_bin(co):
        return int((math.atan2(co.x, -(co.y - v2.AXIS_Y)) / (2 * math.pi) + 0.5) * BINS) % BINS

    def per_bin(pairs, pick):
        out = [None] * BINS
        for b, x in pairs:
            out[b] = x if out[b] is None else pick(out[b], x)
        for _ in range(BINS):  # bins with no vertex take their neighbours'
            if all(x is not None for x in out):
                break
            out = [x if x is not None else next((out[(i + d) % BINS] for d in (1, -1, 2, -2, 3, -3)
                                                 if out[(i + d) % BINS] is not None), None) for i, x in enumerate(out)]
        return out

    def smooth(a, sigma=2.0, reach=6):
        ws = [math.exp(-0.5 * (d / sigma) ** 2) for d in range(-reach, reach + 1)]
        return [sum(w * a[(i + d) % BINS] for w, d in zip(ws, range(-reach, reach + 1))) / sum(ws) for i in range(BINS)]

    rope_loop = [v for f in bm.faces if _region(f, uvl) == "rope" for v in f.verts if abs(v.co.z - rope_z) < 0.006]
    rope_r = per_bin([(az_bin(v.co), radial(v.co)[0]) for v in rope_loop], max)
    typical = sorted(rope_r)[BINS // 2]
    rope_r = [min(x, typical + 0.004) for x in rope_r]  # the knot stands out further than the loop
    top = [v for v in moving if -0.008 < v.co.z - rope_z < 0.0]
    top_r = per_bin([(az_bin(v.co), radial(v.co)[0]) for v in top], max)
    # the rope's knot and ends hang in front of the skirt (and the bands pass by): no push near them
    others = bmesh.new()
    for f in bm.faces:
        r = _region(f, uvl)
        if r in ("bands", "bundle") or (r == "rope" and f.calc_center_median().z < rope_z - 0.008):
            others.faces.new([others.verts.new(v.co) for v in f.verts])
    otree = BVHTree.FromBMesh(others)
    others.free()
    zone = [v for v in moving if -CINCH_H < v.co.z - rope_z < 0.0]
    clear = per_bin([(az_bin(v.co), (otree.find_nearest(v.co)[3] or 1.0) if otree.find_nearest(v.co)[0] else 1.0)
                     for v in zone], min)
    amount = smooth([max(0.0, rope_r[b] - CINCH_IN - top_r[b])
                     * min(1.0, max(0.0, (clear[b] - CLEAR[0]) / (CLEAR[1] - CLEAR[0]))) for b in range(BINS)])
    # the puff's shading from the surface it describes, not from its triangles: the skirt has a ring every 1-4 cm
    # here and in 18:50's low light the triangles between them showed as dark teeth under the rope (worse in tier B,
    # where the wool is decimated). Each vertex keeps the cloth's normal from before the push, tipped down by the
    # puff's slope (a surface r = r0 + k(z) has its normal along d - k'(z) z)
    bm.normal_update()
    pushed, most = 0, 0.0
    for v in zone:
        h = v.co.z - rope_z
        t = min(1.0, -h / CINCH_H)
        bump = 0.5 * (1 + math.cos(math.pi * t))
        r, d = radial(v.co)
        a = amount[az_bin(v.co)]
        n0 = v.normal.copy()
        dk = a * 0.5 * math.pi / CINCH_H * math.sin(math.pi * t)  # dk/dz
        v[puff_n] = (n0 - Vector((0.0, 0.0, dk * max(0.0, n0.dot(d))))).normalized()
        k = a * bump
        if k > 1e-4:
            v.co += d * k
            pushed += 1
            most = max(most, k)
    # the ring above: its shadow at noon may reach NOON_SHADOW below the rope, onto the puffed skirt's top
    base = smooth([top_r[b] + amount[b] for b in range(BINS)])
    slope = math.tan(NOON_SUN)
    pulled = 0
    for v in moving:
        h = v.co.z - rope_z
        if not 0.0 < h < BLOUSE_TOP:
            continue
        r, d = radial(v.co)
        limit = base[az_bin(v.co)] + (h + NOON_SHADOW) / slope
        fade = min(1.0, (BLOUSE_TOP - h) / 0.02)  # back to the cloth as it was at the top of the ring
        if r > limit:
            v.co -= d * (r - limit) * fade
            pulled += 1
    # still they come through the skirt top in some poses (they and the skirt follow the body a little differently):
    # marked, so melos_prep.py gives them the skirt's colour instead of their near-black AO
    mark = bm.faces.layers.int.get(INNER_ATTR) or bm.faces.layers.int.new(INNER_ATTR)
    marked = 0
    for f in bm.faces:
        f[mark] = int(all(v in inner for v in f.verts))
        marked += f[mark]
    return {"cinch_cut_edges": len(cut), "cinch_pushed": pushed, "cinch_most_mm": round(most * 1000, 1),
            "blouse_pulled": pulled, "inner_verts": len(inner), "inner_hugged": hugged, "inner_faces": marked}


def _components(faces):
    faces = set(faces)
    by_vert = {}
    for f in faces:
        for v in f.verts:
            by_vert.setdefault(v, []).append(f)
    seen, comps = set(), []
    for f in faces:
        if f in seen:
            continue
        stack, comp = [f], []
        seen.add(f)
        while stack:
            g = stack.pop()
            comp.append(g)
            for v in g.verts:
                for h in by_vert[v]:
                    if h not in seen:
                        seen.add(h)
                        stack.append(h)
        comps.append(comp)
    return comps


def ears(tunic, bm, uvl, dl):
    """Take the bundle knot's two ends off and put short flat ones on, along the bundle's surface."""
    bundle_g = tunic.vertex_groups["bundle"].index
    on_bundle = [f for f in bm.faces if _region(f, uvl) == "bands"
                 and all(v[dl].get(bundle_g, 0.0) > 0.99 and len(v[dl]) == 1 for v in f.verts)]
    comps = sorted(_components(on_bundle), key=len)
    if len(comps) != 3:
        raise SystemExit(f"expected the back knot and two ends on the bundle, found {[len(c) for c in comps]}")
    *old, knot = comps
    bundle_faces = [f for f in bm.faces if _region(f, uvl) == "bundle"]
    centre = sum((f.calc_center_median() for f in bundle_faces), Vector()) / len(bundle_faces)
    btree = BVHTree.FromBMesh(_copy(bundle_faces))
    # the knot itself stood 3.7 cm off the bundle and its top loop still showed over the outline in the talk view
    # (round 5 check): pressed down to KNOT_FLAT of that, a cloth knot pulled tight
    tallest = 0.0
    for v in {v for f in knot for v in f.verts}:
        q, n, _, _ = btree.find_nearest(v.co)
        if q is None:
            continue
        up = (v.co - q).dot(n)
        if up > 0:
            v.co -= n * up * (1 - KNOT_FLAT)
            tallest = max(tallest, up * KNOT_FLAT)
    kc = sum((v.co for f in knot for v in f.verts), Vector()) / sum(len(f.verts) for f in knot)
    bmesh.ops.delete(bm, geom=[f for c in old for f in c], context="FACES")
    out = (kc - centre).normalized()
    c, s = math.cos(v3.BUNDLE_TILT), math.sin(v3.BUNDLE_TILT)
    ax, az = Vector((c, 0, -s)), Vector((s, 0, c))
    parts = []
    for side, length in zip((-1, 1), EAR_LEN):
        d = ax * side * 0.85 - az * 0.45
        d = (d - out * d.dot(out)).normalized()  # along the bundle's surface
        start = kc + d * 0.012
        pts = []
        for i in range(6):
            p = start + d * length * i / 5
            q, n, _, _ = btree.find_nearest(p)
            pts.append(q + n * 0.004 if q is not None else p)  # lies on the cloth of the bundle
        e = v2._Part(NEW_UV["bands"])
        v3._strand(e, pts, (EAR_W, 0.003), 6, lambda p: {"bundle": 1.0}, v3.BAND_U_M, twist_m=0.25,
                   taper=lambda t: 1.0 - 0.55 * t)
        parts.append(e)
    return parts, {"ears_removed_faces": sum(len(c) for c in old), "knot_at": [round(x, 3) for x in kc],
                   "knot_height_mm": round(tallest * 1000, 1)}


def puff_normals(tunic):
    """The waist's puff normals (PUFF_N) as custom normals; every other corner keeps Blender's own (a zero vector).
    They survive triangulation and decimation (interpolated) and the glTF exporter writes them."""
    me = tunic.data
    attr = me.attributes[PUFF_N]
    n = np.zeros(len(me.vertices) * 3)
    attr.data.foreach_get("vector", n)
    n = n.reshape(-1, 3)
    corner = np.zeros(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", corner)
    me.normals_split_custom_set([tuple(x) for x in n[corner]])
    me.attributes.remove(me.attributes[PUFF_N])
    return int((np.abs(n).sum(1) > 0).sum())


def _copy(faces):
    out = bmesh.new()
    for f in faces:
        out.faces.new([out.verts.new(v.co) for v in f.verts])
    out.normal_update()
    return out


def build(tunic_name="Tunic", body_name="Body"):
    tunic, body = bpy.data.objects[tunic_name], bpy.data.objects[body_name]
    for o in (tunic, body):
        o.data.update()
    report = {}
    me = tunic.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv.active
    dl = bm.verts.layers.deform.verify()
    bm.normal_update()
    report |= waist(bm, uvl, body)
    parts, r = ears(tunic, bm, uvl, dl)
    report |= r
    # v4's rolled edges and the layers behind the rope came out of bmesh extrusions flat-shaded: in poses the layers
    # behind the rope come through the skirt top, and flat they showed as dark teeth under the rope at 18:50
    flat = [f for f in bm.faces if not f.smooth and _region(f, uvl) == "wool"]
    for f in flat:
        f.smooth = True
    report["wool_faces_smoothed"] = len(flat)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()
    v2._add(tunic, parts)
    report["puff_normals"] = puff_normals(tunic)
    report["tunic_tris"] = sum(len(p.vertices) - 2 for p in tunic.data.polygons)
    return report


if __name__ == "__main__" and "--" in sys.argv:
    src, dst = sys.argv[-2], sys.argv[-1]
    bpy.ops.wm.open_mainfile(filepath=src)
    print(build())
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(dst), compress=True)
