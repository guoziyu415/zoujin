"""A-0 v3: Melos's bundle, its bands and the knots again, per UX's round 2 (ux/reviews/a0-melos.md N1-N3).

Runs on melos_v2.blend (Blender on the Mac, or bpy in the container: no MPFB needed). Takes v2's bundle, bands,
chest knot and rope out of `Tunic` (by their UV regions) and builds them again:
- bundle (N1): on the upper back, tilted so its top is towards his right shoulder, about 55 x 40 x 22 cm; a soft
  package of cloth, lumpy where the things inside push out, the cloth gathered in creases towards the knot on its
  back (two corners tied there, their ends sticking up) and towards the two corners that become the bands. Its sides
  round off behind him instead of wrapping forward round his waist (v2's flat "panniers" from the front);
- bands (N3): those two corners twisted into a round strand, over his right shoulder and under his left arm;
- chest knot (N2): the two strands really tied (a knot of the tube, not a ball), their ends out 8-10 cm;
- rope: the same loop at the waist, its knot an overhand knot of the rope, two ends hanging 15 cm.
UVs stay in the v2 regions (melos_tex.py paints them): the bundle's pole is at its back knot, so the texture's creases
run out from there; strands and knots are in "bands", u along the strand (u = metres / BAND_U_M, so the twist painted
on them has the same pitch everywhere), v round it; the rope's u is metres / its loop length, likewise.

Frame: MPFB, metres, +Z up, the character faces -Y, his left is +X (his back is +Y).
"""

import math
import os
import random
import sys

import bpy  # first: bpy as a module brings bmesh and mathutils with it
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import melos_clothes_v2 as v2  # noqa: E402  (its helpers: parts, tubes, weights, UV regions)

NEW_UV = v2.NEW_UV
# bundle: centre height, tilt (its across axis goes down towards his left), half sizes across / deep / up
BUNDLE_Z, BUNDLE_TILT = 1.31, math.radians(15)
BUNDLE_HALF = (0.27, 0.11, 0.19)
BUNDLE_SEGS, BUNDLE_RINGS = 28, 12
# where the cloth gathers, as directions from the bundle's centre in its own frame (x across, y back, z up): the
# knot on its back, and the corners that leave as bands (top on his right, bottom on his left)
GATHER = {"knot": (0.05, 1.0, 0.45), "band_a": (-0.85, 0.15, 0.75), "band_b": (0.9, 0.15, -0.7)}
CREASE_N, CREASE_DEPTH, CREASE_REACH = 6, 0.022, 1.3  # folds round each gather point, depth (m), reach (radians)
PULL = {"knot": 0.025, "band_a": 0.05, "band_b": 0.05}  # the cloth drawn out towards each gather point (m)
BAND_R = (0.012, 0.008)  # a twisted cloth strand: wider than deep, the section turns along it
BAND_TWIST_M = 0.12  # one turn of the section every 12 cm (the texture's twist is finer)
BAND_U_M = 0.8  # metres of strand per unit of u (melos_tex.py: the twist stripes assume this); every strand is shorter
KNOT_CHEST = (0.0, -0.125, 1.28)
CHEST_KNOT_S, CHEST_KNOT_R = 0.0075, 0.010  # trefoil scale (it spans about 6 s across) and strand radius
END_LEN = (0.095, 0.085)  # the two cloth ends out of the chest knot
BACK_KNOT_S, BACK_KNOT_R = 0.009, 0.012
EAR_LEN = (0.07, 0.06)
ROPE_KNOT_S = 0.0042


def _trefoil(t):
    return Vector((math.sin(t) + 2 * math.sin(2 * t), math.cos(t) - 2 * math.cos(2 * t), -math.sin(3 * t)))


def _rmf(path, n0=None, closed=False):
    """Rotation-minimising frames along a path (double reflection): one normal per point. Closed: path[-1] is
    path[0] again, and the tangents wrap round."""
    ts = []
    m = len(path) - 1 if closed else len(path)
    for i in range(len(path)):
        if closed:
            a, b = path[(i + 1) % m], path[(i - 1) % m]
        else:
            a, b = path[min(i + 1, len(path) - 1)], path[max(i - 1, 0)]
        ts.append((a - b).normalized())
    if n0 is None:
        up = Vector((0, 0, 1)) if abs(ts[0].z) < 0.9 else Vector((1, 0, 0))
        n0 = ts[0].cross(up).cross(ts[0])
    ns = [(n0 - ts[0] * n0.dot(ts[0])).normalized()]
    for i in range(len(path) - 1):
        v1 = path[i + 1] - path[i]
        c1 = v1.dot(v1)
        if c1 < 1e-12:
            ns.append(ns[-1].copy())
            continue
        rl = ns[-1] - (2 / c1) * v1.dot(ns[-1]) * v1
        tl = ts[i] - (2 / c1) * v1.dot(ts[i]) * v1
        v2_ = ts[i + 1] - tl
        c2 = v2_.dot(v2_)
        ns.append((rl - (2 / c2) * v2_.dot(rl) * v2_ if c2 > 1e-12 else rl).normalized())
    return ts, ns


def _strand(part, path, radius, sides, weights_at, u_m, twist_m=None, closed=False, n0=None, taper=None):
    """A tube along `path` with an elliptical section radius = (rx, ry) that turns once every `twist_m` metres;
    `taper(s)` (s 0..1 along) scales the section. UV u = metres along / u_m, v round it. Returns the length."""
    if closed:
        path = path + [path[0]]
    ts, ns = _rmf(path, n0, closed)
    if closed:  # spread the frame's mismatch at the seam along the loop
        b0 = ts[0].cross(ns[0])
        miss = math.atan2(ns[-1].dot(b0), ns[-1].dot(ns[0]))
    else:
        miss = 0.0
    total = sum((path[i + 1] - path[i]).length for i in range(len(path) - 1))
    turns = total / twist_m if twist_m else 0.0
    if closed:
        turns = round(turns)  # whole turns, so the section meets itself at the seam
    rings, s = [], 0.0
    for i, c in enumerate(path):
        if i:
            s += (path[i] - path[i - 1]).length
        n = ns[i]
        b = ts[i].cross(n)
        f = s / total if total else 0.0
        ang = (2 * math.pi * turns - miss) * f
        n, b = n * math.cos(ang) + b * math.sin(ang), b * math.cos(ang) - n * math.sin(ang)
        if closed and i == len(path) - 1:
            rings.append((rings[0][0], s / u_m))
            break
        k = taper(s / total) if taper else 1.0
        w = weights_at(c)
        ring = []
        for j in range(sides):
            a = 2 * math.pi * j / sides
            ring.append(part.vert(c + k * (radius[0] * math.cos(a) * n + radius[1] * math.sin(a) * b), w))
        rings.append((ring, s / u_m))
    for i in range(len(rings) - 1):
        (r0, u0), (r1, u1) = rings[i], rings[i + 1]
        for j in range(sides):
            j1 = (j + 1) % sides
            part.face((r0[j], r1[j], r1[j1], r0[j1]), [(u0, j / sides), (u1, j / sides), (u1, (j + 1) / sides),
                                                       (u0, (j + 1) / sides)])
    if not closed:  # caps: fans to a centre point, the cloth end
        for (ring, u), sign in ((rings[0], -1), (rings[-1], 1)):
            ctr = sum((part.co[i] for i in ring), Vector()) / len(ring)
            c = part.vert(ctr, part.w[ring[0]])
            for j in range(sides):
                j1 = (j + 1) % sides
                idx = (ring[j], ring[j1], c) if sign > 0 else (ring[j1], ring[j], c)
                part.face(idx, [(u, j / sides), (u, (j + 1) / sides), (u, (j + 0.5) / sides)])
    return total


def _knot(part, centre, scale, radius, facing, up, weights_at, u_m, segs, sides, seed):
    """A tied knot: a trefoil of the strand, its flat side towards `facing`, a little irregular."""
    rnd = random.Random(seed)
    f = Vector(facing).normalized()
    x = Vector(up).cross(f).normalized()
    y = f.cross(x)
    m = Matrix((x, y, f)).transposed()  # trefoil (x, y) in the plane across `facing`, its z along it
    jit = [rnd.uniform(-0.12, 0.12) for _ in range(6)]
    path = []
    for i in range(segs):
        t = 2 * math.pi * i / segs
        p = _trefoil(t)
        p.z *= 1.4  # the crossings stand off each other a little more: reads as tied, not flat
        k = 1 + sum(a * math.sin((j + 2) * t + j) for j, a in enumerate(jit)) * 0.5
        path.append(Vector(centre) + m @ (p * scale * k))
    _strand(part, path, (radius, radius * 0.85), sides, weights_at, u_m, twist_m=BAND_TWIST_M, closed=True)
    return path


def _end(part, start, direction, length, width, weights_at, u_m, droop=0.35, curl=0.0):
    """A cloth end out of a knot: a flattened, tapering strand that droops."""
    d = Vector(direction).normalized()
    pts = []
    for i in range(7):
        s = i / 6
        p = Vector(start) + d * length * s + Vector((0, 0, -droop * length * s * s))
        p += d.cross(Vector((0, 0, 1))).normalized() * curl * length * math.sin(math.pi * s)
        pts.append(p)
    _strand(part, pts, (width, 0.0035), 6, weights_at, u_m, twist_m=0.25, taper=lambda s: 1.0 - 0.6 * s)


def strip_v2(tunic, rig):
    """Delete v2's bundle, bands, chest knot and rope from the tunic (faces in those UV regions)."""
    me = tunic.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv.active
    gone = []
    for f in bm.faces:
        u = sum(lp[uvl].uv.x for lp in f.loops) / len(f.loops)
        v = sum(lp[uvl].uv.y for lp in f.loops) / len(f.loops)
        for name in ("bundle", "bands", "rope"):
            u0, u1, v0, v1 = NEW_UV[name]
            if u0 <= u < u1 and v0 <= v < v1:
                gone.append(f)
                break
    n = len(gone)
    bmesh.ops.delete(bm, geom=gone, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()
    return n


def _back_y(skin, x, z):
    """His back's surface (y) at (x, z), and beyond the shoulder blades a gentle fall-off."""
    xc = max(-0.15, min(0.15, x))
    hit = skin.ray_cast(Vector((xc, 0.6, z)), Vector((0, -1, 0)), 1.0)
    y = hit[0].y if hit[0] is not None else 0.12
    return y - 0.12 * max(0.0, abs(x) - 0.15)


def bundle(body, rig):
    skin = v2._torso_bvh(body)
    c, s = math.cos(BUNDLE_TILT), math.sin(BUNDLE_TILT)
    ax = Vector((c, 0, -s))  # across: down towards his left (+x)
    az = Vector((s, 0, c))
    ay = Vector((0, 1, 0))
    yb = _back_y(skin, 0.0, BUNDLE_Z)
    centre = Vector((-0.01, yb + 0.016 + BUNDLE_HALF[1], BUNDLE_Z))
    rnd = random.Random(11)
    lumps = [(Vector([rnd.uniform(-1, 1) for _ in range(3)]).normalized(), rnd.uniform(0.6, 1.0)) for _ in range(8)]
    gathers = []
    for key, g in GATHER.items():
        g = Vector(g).normalized()
        e1 = g.cross(Vector((0, 0, 1)) if abs(g.z) < 0.9 else Vector((1, 0, 0))).normalized()
        gathers.append((g, e1, g.cross(e1), PULL[key]))

    def local(d):
        e = [math.copysign(abs(q) ** 0.6, q) for q in d]  # boxy: a package of things in a cloth
        p = Vector((e[0] * BUNDLE_HALF[0], e[1] * BUNDLE_HALF[1], e[2] * BUNDLE_HALF[2]))
        p.x *= 1 + 0.07 * max(0.0, -e[2])  # sags wider at the bottom
        bump = sum(a * math.exp((d.dot(q) - 1) / 0.09) for q, a in lumps)
        fold, pull = 0.0, Vector()
        for g, e1, e2, k in gathers:
            ang = math.acos(max(-1.0, min(1.0, d.dot(g))))
            if ang < CREASE_REACH:
                phi = math.atan2(d.dot(e2), d.dot(e1))
                fade = (1 - ang / CREASE_REACH) ** 1.5
                # creases radiate from the gather point and get deeper towards it; the cloth is drawn out there
                fold += fade * (0.5 + 0.5 * math.cos(CREASE_N * phi + 2 * ang + 0.7 * math.sin(3 * phi)))
                pull += Vector((g.x * BUNDLE_HALF[0], g.y * BUNDLE_HALF[1], g.z * BUNDLE_HALF[2])).normalized() * (
                    k * fade ** 3)
        n = p.normalized()
        return p + pull + n * (0.026 * bump - CREASE_DEPTH * fold + 0.003 * (rnd.random() - 0.5)), d

    def place(d):
        p, _ = local(d)
        w = centre + ax * p.x + ay * p.y + az * p.z
        w.y = max(w.y, _back_y(skin, w.x, w.z) + 0.014)  # pressed against his back, never into it
        return w

    # the UV sphere's pole at the back knot, so melos_tex.py's creases run out from it
    pole = Vector(GATHER["knot"]).normalized()
    q = Vector((0, 0, 1)).rotation_difference(pole)
    part = v2._Part(NEW_UV["bundle"])
    v2._sphere(part, lambda d: place(q @ d), lambda p: {"bundle": 1.0}, BUNDLE_SEGS, BUNDLE_RINGS)

    def at(d):
        return place(Vector(d).normalized())

    # its bone, as v2: in the middle against the back, upwards, under spine_03
    vl = bpy.context.view_layer
    was = vl.objects.active
    if was is not None and was.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    rig.hide_set(False)
    vl.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    eb = rig.data.edit_bones.get("bundle") or rig.data.edit_bones.new("bundle")
    eb.head = (0.0, yb + 0.02, BUNDLE_Z + 0.05)
    eb.tail = (0.0, yb + 0.02, BUNDLE_Z + 0.15)
    eb.parent = rig.data.edit_bones["spine_03"]
    eb.use_connect = False
    eb.use_deform = True
    bpy.ops.object.mode_set(mode="OBJECT")
    vl.objects.active = was

    # the knot on its back and the two corner ends sticking up out of it
    kd = Vector(GATHER["knot"]).normalized()
    kp = at(GATHER["knot"])
    out = (kp - centre).normalized()
    knot = v2._Part(NEW_UV["bands"])
    _knot(knot, kp + out * (BACK_KNOT_R * 0.6), BACK_KNOT_S, BACK_KNOT_R, out, az, lambda p: {"bundle": 1.0},
          BAND_U_M, 30, 6, 21)
    ears = []
    for side, length in zip((-1, 1), EAR_LEN):
        e = v2._Part(NEW_UV["bands"])
        d = (az * 0.8 + ax * side * 0.6 + out * 0.5).normalized()
        _end(e, kp + out * BACK_KNOT_R + d * 0.02, d, length, 0.016, lambda p: {"bundle": 1.0}, BAND_U_M,
             droop=0.25, curl=0.15 * side)
        ears.append(e)
    corners = {k: at(GATHER[k]) for k in ("band_a", "band_b")}
    return [part, knot] + ears, corners, centre, kd


def bands_and_knot(tunic, body, rig, corners):
    """The two corners twisted into strands: A from the bundle's top corner over his right shoulder, B from its
    bottom corner under his left arm, both to the chest knot; the knot, and the two ends out of it."""
    skin = v2._torso_bvh(body)
    cloth = BVHTree.FromObject(tunic, bpy.context.evaluated_depsgraph_get(), deform=False)
    bones = {b.name for b in rig.data.bones}
    from_body = v2._weights_from(body, body.matrix_world)

    def w(c):
        return from_body(c, bones)

    p, n, _, _ = skin.find_nearest(Vector(KNOT_CHEST))
    knot_at = p + n * ((v2._offset_to(cloth, p, n) or 0.0) + 0.014)
    # rough routes over the skin (v2's, ending at the new corners)
    routes = {
        "band_a": [(-0.04, -0.12, 1.34), (-0.09, -0.09, 1.41), (-0.12, -0.02, 1.465), (-0.13, 0.06, 1.46)],
        "band_b": [(0.08, -0.11, 1.255), (0.14, -0.06, 1.225), (0.165, 0.02, 1.2)],
    }
    pieces, lengths = [], {}
    for name, route in routes.items():
        path = v2._catmull([tuple(knot_at)] + route + [tuple(corners[name])], step=0.02)
        hits = [skin.find_nearest(c) for c in path]
        offs = v2._smooth([(v2._offset_to(cloth, q, m) or 0.0) + BAND_R[0] + 0.002 for q, m, _, _ in hits])
        pts = []
        for i, ((q, m, _, _), off) in enumerate(zip(hits, offs)):
            # on him it lies on the skin (or the cloth); where the route leaves him (into the knot, across to the
            # bundle's corner) it follows the route
            t = min(1.0, max(0.0, ((path[i] - q).length - 0.03) / 0.04))
            on = q + m * off
            pts.append(on.lerp(path[i], t))
        part = v2._Part(NEW_UV["bands"])
        lengths[name] = _strand(part, pts, BAND_R, 6, w, BAND_U_M, twist_m=BAND_TWIST_M)
        pieces.append(part)
    knot = v2._Part(NEW_UV["bands"])
    _knot(knot, knot_at, CHEST_KNOT_S, CHEST_KNOT_R, n, Vector((0, 0, 1)), w, BAND_U_M, 40, 6, 5)
    pieces.append(knot)
    # the two ends: out of the knot, down and a little apart (8-10 cm)
    for side, length in zip((-1, 1), END_LEN):
        e = v2._Part(NEW_UV["bands"])
        d = (Vector((0, 0, -1)) + Vector((side * 0.45, 0, 0)) + n * 0.35).normalized()
        _end(e, knot_at + d * 0.022, d, length, 0.014, w, BAND_U_M, droop=0.15, curl=0.1 * side)
        pieces.append(e)
    assert max(lengths.values()) < BAND_U_M, lengths  # u stays inside the region
    return pieces, lengths


def rope(tunic, body, rig):
    """v2's loop at the waist, then an overhand knot of the rope at his front left and its two ends."""
    skin = v2._torso_bvh(body)
    cloth = BVHTree.FromObject(tunic, bpy.context.evaluated_depsgraph_get(), deform=False)
    bones = {b.name for b in rig.data.bones}
    from_tunic = v2._weights_from(tunic, tunic.matrix_world)

    def w(c):
        return from_tunic(c, bones)

    axis = Vector((0, v2.AXIS_Y, v2.ROPE_Z))
    ring = []
    for i in range(v2.ROPE_SEG):
        th = 2 * math.pi * i / v2.ROPE_SEG
        d = Vector((math.sin(th), -math.cos(th), 0))
        p, n, _, _ = skin.ray_cast(axis + d * 0.4, -d, 0.4)
        off = max(v2._offset_to(cloth, p, n) or 0.0, v2.CINCH) + v2.ROPE_R + 0.001
        ring.append(p + n * off)
    loop_len = sum((ring[(i + 1) % len(ring)] - ring[i]).length for i in range(len(ring)))
    loop = v2._Part(NEW_UV["rope"])
    v2._tube(loop, ring + [ring[0]], v2.ROPE_R, 6, w)  # v2's tube: u 0..1 round the loop, as melos_tex.py paints
    kd = Vector((0.6, -0.8, 0)).normalized()
    at = max(ring, key=lambda c: (c - axis).normalized().dot(kd))
    out = Vector((at.x, at.y - v2.AXIS_Y, 0)).normalized()
    knot = v2._Part(NEW_UV["rope"])
    centre = at + out * (v2.ROPE_R * 2.2)
    _knot(knot, centre, ROPE_KNOT_S, v2.ROPE_R, out, Vector((0, 0, 1)), w, loop_len, 28, 5, 3)
    pieces = [loop, knot]
    for side in (-1, 1):
        tail = v2._Part(NEW_UV["rope"])
        start = centre + Vector((0, 0, -0.012))
        across = Vector((out.y, -out.x, 0)) * side
        path = [start + across * 0.006 * (s / 6) ** 0.5 + out * 0.012 * math.sin(math.pi * s / 12)
                + Vector((0, 0, -v2.TAIL_LEN * s / 6)) for s in range(7)]
        _strand(tail, path, (v2.ROPE_R * 0.9, v2.ROPE_R * 0.9), 5, w, loop_len)
        pieces.append(tail)
    return pieces


def build(tunic_name="Tunic", body_name="Body", rig_name="Rig"):
    tunic, body, rig = (bpy.data.objects[n] for n in (tunic_name, body_name, rig_name))
    for o in (tunic, body):
        o.data.update()
    removed = strip_v2(tunic, rig)
    parts, corners, centre, _ = bundle(body, rig)
    bands, lengths = bands_and_knot(tunic, body, rig, corners)
    parts += bands + rope(tunic, body, rig)
    v2._add(tunic, parts)
    return {"removed_faces": removed, "tunic_tris": sum(len(p.vertices) - 2 for p in tunic.data.polygons),
            "bundle_centre": [round(x, 3) for x in centre], "band_lengths": {k: round(x, 3) for k, x in lengths.items()},
            "bones": len(rig.data.bones)}


if __name__ == "__main__" and "--" in sys.argv:
    # bpy in the container: <python> melos_clothes_v3.py -- <melos_v2.blend> <out.blend>
    src, dst = sys.argv[-2], sys.argv[-1]
    bpy.ops.wm.open_mainfile(filepath=src)
    print(build())
    bpy.ops.wm.save_as_mainfile(filepath=dst)
