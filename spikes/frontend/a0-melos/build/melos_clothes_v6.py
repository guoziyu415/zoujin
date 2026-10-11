"""A-0 v6: Melos's armpit and rope per UX's round 6 (ux/reviews/a0-melos.md, round 6, B and C).

Runs on the output of melos_clothes_v5.py (bpy in the container): <python> melos_clothes_v6.py -- <v5.blend> <out.blend>

- armpit (B): at noon a pale grey oval and a black slit showed in his left armhole in the talk view. The oval is the
  side of his chest; the slit is the inside of the tunic's back, seen past the edge of the skin that `__under_tunic`
  deletes. With his arms down (the idle and talk poses) the armhole opens wider than in the rest pose the group was
  made in. Skin under the cloth within ARMPIT_KEEP of the upper arm in the talk pose now stays (below the shoulder,
  where the cloth hangs loose). The oval was pale because its AO was baked with the arms out: melos_prep.py bakes it
  again with the arms down (talk_pose below);
- rope (C): right of the knot the rope bent down into a sharp V about 4 cm deep and back up, like bent wire. Its
  points had uneven bone weights (some all pelvis, their neighbours half spine, the knot a quarter left thigh), so in
  the idle pose they moved apart. The loop and the knot now take the weights of the cloth under them, smoothed round
  the waist. The two ends were straight rods with square tips: now they hang in a soft curve over the puffed skirt,
  one longer than the other, and taper to a rounded tip; they move with the knot, 4 mm off the skirt.

Frame: MPFB, metres, +Z up, the character faces -Y, his left is +X.
"""

import math
import os
import sys

import bpy  # first: bpy as a module brings bmesh and mathutils with it
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import melos_clothes_v2 as v2  # noqa: E402
import melos_clothes_v3 as v3  # noqa: E402
import melos_clothes_v4 as v4  # noqa: E402
import melos_clothes_v5 as v5  # noqa: E402

NEW_UV = v2.NEW_UV
# upper and lower arm directions in the idle pose the talk view holds (rig space; read off the test page's skeleton)
TALK_DIRS = {
    "upperarm_l": (0.341, 0.170, -0.924),
    "lowerarm_l": (0.168, -0.310, -0.936),
    "upperarm_r": (-0.173, 0.429, -0.887),
    "lowerarm_r": (-0.225, -0.314, -0.923),
}
ARMPIT_KEEP = 0.07  # skin under the cloth this close to the upper arm in the talk pose stays (m)
ARMPIT_BELOW = 0.06  # ... and only this far under the shoulder joint and lower: on the shoulder the cloth lies tight
WEIGHT_SIGMA = math.radians(14)  # smoothing of the rope's weights round the waist
# the ends, the one on his right first: length, drift across at the tip (+ towards his left), how far it bows out
TAILS = ((0.12, -0.015, 0.015), (0.15, 0.035, 0.010))
TAIL_SIDES, TAIL_PTS = 6, 14
TAIL_TIP = 0.45  # the tip's radius, of the rope's
# the ends stay this far off the cloth. They move with the knot: the skirt under them follows the thigh, and ends
# that took the skirt's weights (all or part) bent into segments in the idle pose, where pelvis and thigh mix
TAIL_GAP = 0.004


def talk_pose(rig):
    """Turn the arms down as in the idle pose (parents first). Undo with rest_pose."""
    rig.data.pose_position = "POSE"
    inv = rig.matrix_world.inverted().to_3x3()
    for name in ("upperarm_l", "lowerarm_l", "upperarm_r", "lowerarm_r"):
        bpy.context.view_layer.update()
        pb = rig.pose.bones[name]
        h = pb.head.copy()
        rot = (pb.tail - h).normalized().rotation_difference((inv @ Vector(TALK_DIRS[name])).normalized())
        pb.matrix = Matrix.Translation(h) @ rot.to_matrix().to_4x4() @ Matrix.Translation(-h) @ pb.matrix
    bpy.context.view_layer.update()


def rest_pose(rig):
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def _posed_coords(ob):
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    co = [ob.matrix_world @ v.co for v in me.vertices]
    ev.to_mesh_clear()
    return co


def armpit_skin(body, tunic, rig):
    """Take the skin near the upper arm (in the talk pose) out of `__under_tunic`. Reports how much stays, and how many
    of those vertices end up outside the cloth in that pose (they would show through it)."""
    g = body.vertex_groups["__under_tunic"]
    bw = v4._body_weights(body, rig)
    covered = [v.index for v in body.data.vertices if any(x.group == g.index and x.weight > 0 for x in v.groups)]
    shoulder = {s: rig.matrix_world @ rig.data.bones["upperarm_" + s].head_local for s in "lr"}
    talk_pose(rig)
    try:
        co = _posed_coords(body)
        tco = _posed_coords(tunic)
        tme = tunic.data
        ttree = BVHTree.FromPolygons(tco, [p.vertices[:] for p in tme.polygons])
    finally:
        rest_pose(rig)
    arm = [i for i, w in enumerate(bw) if w and max(w, key=w.get).startswith(("upperarm", "lowerarm"))]
    kd = KDTree(len(arm))
    for i in arm:
        kd.insert(co[i], i)
    kd.balance()
    rest = body.matrix_world
    free, outside = [], 0
    for i in covered:
        z = (rest @ body.data.vertices[i].co).z
        side = "l" if (rest @ body.data.vertices[i].co).x > 0 else "r"
        if z > shoulder[side].z - ARMPIT_BELOW:
            continue
        _, _, d = kd.find(co[i])
        if d is None or d > ARMPIT_KEEP:
            continue
        free.append(i)
        q, n, _, _ = ttree.find_nearest(co[i])
        if q is not None and (co[i] - q).dot(n) > 0:  # cloth normals point out: the skin is past it
            outside += 1
    g.remove(free)
    return {"armpit_skin_kept": len(free), "armpit_skin_outside_cloth": outside}


def _rope_parts(bm, uvl):
    rope = [f for f in bm.faces if v5._region(f, uvl) == "rope"]
    comps = v5._components(rope)
    if len(comps) != 4:
        raise SystemExit(f"expected the rope's loop, knot and two ends, found {[len(c) for c in comps]}")

    def span(c):
        zs = [v.co.z for f in c for v in f.verts]
        return max(zs) - min(zs)

    def reach(c):
        az = [v5._azimuth(v.co) for f in c for v in f.verts]
        return max(az) - min(az)

    loop = max(comps, key=reach)
    rest = [c for c in comps if c is not loop]
    tails = sorted(rest, key=span)[-2:]
    knot = next(c for c in rest if c not in tails)
    return loop, knot, tails


def _cloth_weights(bm, uvl, dl, names, inner_layer):
    """Bone weights of the outer cloth (not the layers behind the rope), as a function of a point: the nearest few
    cloth vertices', inverse-distance."""
    inner = {f.index for f in bm.faces if inner_layer is not None and f[inner_layer]}
    verts = [v for v in bm.verts
             if any(v5._region(f, uvl) == "wool" for f in v.link_faces)
             and not all(f.index in inner for f in v.link_faces)]
    kd = KDTree(len(verts))
    for i, v in enumerate(verts):
        kd.insert(v.co, i)
    kd.balance()

    def at(p, k=6):
        acc, tot = {}, 0.0
        for _, i, d in kd.find_n(p, k):
            s = 1.0 / max(d, 0.002)
            for g, x in verts[i][dl].items():
                if g in names:
                    acc[g] = acc.get(g, 0.0) + s * x
            tot += s
        return {g: x / tot for g, x in acc.items()}

    return at


def _clean(w, keep=4):
    top = sorted(w.items(), key=lambda kv: -kv[1])[:keep]
    top = [(g, x) for g, x in top if x > 0.02]
    s = sum(x for _, x in top) or 1.0
    return {g: x / s for g, x in top}


def _set(v, dl, w):
    v[dl].clear()
    for g, x in w.items():
        v[dl][g] = x


def rope(tunic, rig, bm, uvl, dl):
    """Even weights for the loop and the knot; the two ends built again, curved and tapering."""
    names = {g.index for g in tunic.vertex_groups if g.name in v4._bones(rig)}
    inner_layer = bm.faces.layers.int.get(v5.INNER_ATTR)
    loop, knot, tails = _rope_parts(bm, uvl)
    cloth_at = _cloth_weights(bm, uvl, dl, names, inner_layer)
    # the cloth's weights round the waist, every 5 degrees at the rope's height, smoothed round the loop
    loop_verts = {v for f in loop for v in f.verts}
    n = 72
    bins = [[] for _ in range(n)]
    for v in loop_verts:
        bins[int((v5._azimuth(v.co) + math.pi) / (2 * math.pi) * n) % n].append(v.co)
    raw = []
    for i, pts in enumerate(bins):
        if pts:
            c = sum(pts, Vector()) / len(pts)
        else:
            a = (i + 0.5) / n * 2 * math.pi - math.pi
            c = Vector((math.sin(a) * 0.15, v2.AXIS_Y - math.cos(a) * 0.15, v2.ROPE_Z))
        raw.append(cloth_at(c))
    groups = sorted({g for w in raw for g in w})
    m = np.array([[w.get(g, 0.0) for g in groups] for w in raw])
    d = np.arange(n)[:, None] - np.arange(n)[None, :]
    d = np.minimum(np.abs(d), n - np.abs(d)) * (2 * math.pi / n)
    k = np.exp(-0.5 * (d / WEIGHT_SIGMA) ** 2)
    m = (k @ m) / k.sum(1, keepdims=True)

    def round_waist(a):
        f = (a + math.pi) / (2 * math.pi) * n - 0.5
        i0 = int(math.floor(f)) % n
        t = f - math.floor(f)
        row = m[i0] * (1 - t) + m[(i0 + 1) % n] * t
        return _clean({g: float(x) for g, x in zip(groups, row)})

    before = {}
    for v in loop_verts:
        before[v.index] = dict(v[dl])
        _set(v, dl, round_waist(v5._azimuth(v.co)))
    knot_verts = {v for f in knot for v in f.verts}
    kc = sum((v.co for v in knot_verts), Vector()) / len(knot_verts)
    w_knot = round_waist(v5._azimuth(kc))
    for v in knot_verts:
        _set(v, dl, w_knot)
    moved = sum(1 for v in loop_verts if any(abs(before[v.index].get(g, 0) - x) > 0.1 for g, x in v[dl].items()))

    # the ends: where they leave the knot, then rebuilt
    tops = []
    for c in tails:
        vs = {v for f in c for v in f.verts}
        tops.append(max(vs, key=lambda v: v.co.z).co.copy())
    bmesh.ops.delete(bm, geom=list({f for c in tails for f in c}), context="FACES")
    knot_named = {tunic.vertex_groups[g].name: x for g, x in w_knot.items()}
    bm.normal_update()
    wool = [f for f in bm.faces if v5._region(f, uvl) == "wool"]
    ctree = BVHTree.FromBMesh(v5._copy(wool))
    out = Vector((kc.x, kc.y - v2.AXIS_Y, 0)).normalized()
    across = Vector((-out.y, out.x, 0))  # round the waist towards his left
    if across.x < 0:
        across = -across
    ring = [sum(b, Vector()) / len(b) for b in bins if b]
    loop_len = sum((ring[(i + 1) % len(ring)] - ring[i]).length for i in range(len(ring)))  # v3: u = metres / this
    parts, lengths = [], []
    for (length, drift, curl), top in zip(TAILS, sorted(tops, key=lambda p: p.dot(across))):
        start = Vector((top.x, top.y, min(top.z, kc.z - 0.012)))
        pts = []
        for i in range(TAIL_PTS):
            s = i / (TAIL_PTS - 1)
            p = start + Vector((0, 0, -length * s)) + across * drift * s * s + out * curl * math.sin(math.pi * s * 0.9)
            pts.append(p)
        # off the cloth (the skirt puffs out under the rope), then smoothed so the push leaves no kink
        for _ in range(3):
            for i, p in enumerate(pts):
                r = v2.ROPE_R * 0.9 * _taper(i / (TAIL_PTS - 1))
                q, nq, _, _ = ctree.find_nearest(p)
                if q is not None and (p - q).dot(nq) < r + TAIL_GAP:
                    pts[i] = q + nq * (r + TAIL_GAP)
            pts = [pts[0]] + [(pts[i - 1] + 2 * pts[i] + pts[i + 1]) / 4 for i in range(1, TAIL_PTS - 1)] + [pts[-1]]

        part = v2._Part(NEW_UV["rope"])
        lengths.append(v3._strand(part, pts, (v2.ROPE_R * 0.9, v2.ROPE_R * 0.9), TAIL_SIDES, lambda p: knot_named,
                                  loop_len, taper=_taper))
        _round_tip(part, TAIL_SIDES)
        parts.append(part)
    return parts, {"rope_loop_verts_reweighted": moved, "rope_knot_weights": {tunic.vertex_groups[g].name: round(x, 2)
                   for g, x in w_knot.items()}, "rope_tail_lengths": [round(x, 3) for x in lengths]}


def _taper(s):
    t = min(max((s - 0.62) / 0.38, 0.0), 1.0)
    return 1.0 - (1.0 - TAIL_TIP) * t * t * (3 - 2 * t)


def _round_tip(part, sides):
    """v3's strand ends in a flat fan; pull the tip's centre out along the strand so the end is rounded, not square."""
    tip = len(part.co) - 1  # the last cap's centre (v3._strand adds it last)
    ring = part.co[tip - 1 - sides : tip - 1]
    if len(ring) != sides:
        return
    prev = part.co[tip - 1 - 2 * sides : tip - 1 - sides]
    ctr = sum(ring, Vector()) / sides
    back = sum(prev, Vector()) / len(prev) if prev else ctr - Vector((0, 0, 0.01))
    r = sum((p - ctr).length for p in ring) / sides
    part.co[tip] = ctr + (ctr - back).normalized() * r * 0.8


def _add_to(bm, uvl, dl, tunic, parts):
    """v2._add on an open bmesh (the tunic carries custom normals since v5: one round trip, not two)."""
    gidx = {g.name: g.index for g in tunic.vertex_groups}
    for part in parts:
        vs = []
        for p, w in zip(part.co, part.w):
            v = bm.verts.new(p)
            for name, x in w.items():
                if name not in gidx:
                    gidx[name] = tunic.vertex_groups.new(name=name).index
                v[dl][gidx[name]] = x
            vs.append(v)
        u0, u1, v0, v1 = part.region
        u0, u1, v0, v1 = u0 + v2.UV_MARGIN, u1 - v2.UV_MARGIN, v0 + v2.UV_MARGIN, v1 - v2.UV_MARGIN
        new = []
        for idx, uvs in part.faces:
            f = bm.faces.new([vs[i] for i in idx])
            f.material_index = 0
            f.smooth = True
            for lp, (u, v) in zip(f.loops, uvs):
                lp[uvl].uv = (u0 + u * (u1 - u0), v0 + v * (v1 - v0))
            new.append(f)
        if part.outward:
            bmesh.ops.recalc_face_normals(bm, faces=new)


def build(tunic_name="Tunic", body_name="Body", rig_name="Rig"):
    tunic, body, rig = (bpy.data.objects[n] for n in (tunic_name, body_name, rig_name))
    for o in (tunic, body):
        o.data.update()
    report = armpit_skin(body, tunic, rig)
    me = tunic.data
    wool_n0 = _wool_normals(me)
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv.active
    dl = bm.verts.layers.deform.verify()
    bm.normal_update()
    parts, r = rope(tunic, rig, bm, uvl, dl)
    report |= r
    _add_to(bm, uvl, dl, tunic, parts)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()
    wool_n1 = _wool_normals(me)
    report["wool_normals_kept"] = bool(len(wool_n0) == len(wool_n1) and np.abs(wool_n0 - wool_n1).max() < 1e-3)
    report["tunic_tris"] = sum(len(p.vertices) - 2 for p in me.polygons)
    return report


def _wool_normals(me):
    """Corner normals of the wool faces, in face order (the rope's faces come after them and change)."""
    uv = me.uv_layers.active.data
    out = []
    cn = me.corner_normals
    for p in me.polygons:
        u = sum(uv[i].uv.x for i in p.loop_indices) / p.loop_total
        if u < NEW_UV["wool"][1]:
            out.extend(cn[i].vector[:] for i in p.loop_indices)
    return np.array(out)


if __name__ == "__main__" and "--" in sys.argv:
    src, dst = sys.argv[-2], sys.argv[-1]
    bpy.ops.wm.open_mainfile(filepath=src)
    print(build())
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(dst), compress=True)
