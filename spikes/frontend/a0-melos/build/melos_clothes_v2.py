"""A-0 v2: Melos's clothes per the style guide (docs/ux/style-guide/characters/melos.md) and UX's review of v1.

Runs inside Blender on the Mac after melos_clothes.py, on the `Tunic` it made (the MPFB helper garments are gone from
the body by then, so v2 reshapes v1 instead of cutting the helpers again):
- skirt: hem 12 cm above the knee, hangs along the legs (flare 10% -> 4%) in vertical folds, slit on his right side
  from the hem to the hip;
- torso: cinched at the rope and bloused 5-8 cm above it (the dagger hides in there);
- the wide belt becomes a rope of undyed wool, 1 cm thick, knotted at his front left, two ends hanging 15 cm;
- a bundle on his back (55 x 39 x 22 cm, from behind it shows on both sides of him from the front) with its own
  bone `bundle` under spine_03, tied with two bands, over the right shoulder and under the left arm, to a knot on
  the chest.
Everything stays in `Tunic` (one material, one 1024 texture made by melos_tex.py); the UV regions are NEW_UV.
New parts take their bone weights from the nearest vertex of the body or the skirt; the bundle is on its bone only.

Frame: MPFB, metres, +Z up, the character faces -Y, his left is +X.
"""

import math
import random

import bmesh
import bpy
from mathutils import Vector, kdtree
from mathutils.bvhtree import BVHTree

KNEE_Z = 0.509  # calf_l head
HEM_Z = KNEE_Z + 0.12
BELT_Z = (1.015, 1.045)  # v1: the torso ends at the first, the skirt starts at the second
OLD_HEM_Z, OLD_FLARE, NEW_FLARE = 0.60, 0.10, 0.04
AXIS_Y = 0.005
FOLDS, FOLD_AMP = 15, 0.010  # vertical folds round the skirt, deepest at the hem
SLIT_TOP, SLIT_GAP = 0.80, 0.025  # his right side, open by SLIT_GAP at the hem
ROPE_Z, ROPE_R, ROPE_SEG = 1.03, 0.005, 48
TORSO_CUT = ROPE_Z - 0.004  # the torso's lower edge hides under the rope
BLOUSE_H, BLOUSE_PUSH = 0.075, 0.02  # the bloused ring above the rope: height, extra stand-off at its middle
CINCH = 0.007  # cloth stand-off at the rope
TAIL_LEN = 0.15
BUNDLE_C_Z = 1.20
BUNDLE_HALF = (0.275, 0.11, 0.195)  # x (across his back), y (depth), z
BAND_HALF_W = 0.025
OLD_UV = {"belt": (0.75, 1.0, 0.0, 0.4), "straps": (0.75, 1.0, 0.4, 0.7), "soles": (0.75, 1.0, 0.7, 1.0)}
NEW_UV = {
    "wool": (0.0, 0.62, 0.0, 1.0),
    "bundle": (0.62, 1.0, 0.0, 0.45),
    "bands": (0.62, 1.0, 0.45, 0.6),
    "rope": (0.62, 1.0, 0.6, 0.7),
    "straps": (0.62, 1.0, 0.7, 0.85),
    "soles": (0.62, 1.0, 0.85, 1.0),
}
UV_MARGIN = 4 / 1024  # new pieces stay this far inside their region, so mipmaps don't bleed the next colour in
# the bands, as rough points near the skin (snapped to it): knot on the chest, over his right shoulder to the top of
# the bundle; and from the knot under his left arm to its left side
BAND_A = [
    (0.0, -0.125, 1.28),
    (-0.04, -0.12, 1.34),
    (-0.09, -0.09, 1.41),
    (-0.12, -0.02, 1.465),
    (-0.12, 0.06, 1.45),
    (-0.11, 0.12, 1.36),
]
BAND_B = [
    (0.0, -0.125, 1.28),
    (0.08, -0.11, 1.255),
    (0.14, -0.06, 1.225),
    (0.165, 0.02, 1.21),
    (0.13, 0.10, 1.21),
    (0.09, 0.13, 1.22),
]
KNOT_CHEST = (0.0, -0.125, 1.28)


def _in(uv, r):
    return r[0] <= uv.x <= r[1] and r[2] <= uv.y <= r[3]


def _remap(uv, a, b):
    uv.x = b[0] + (uv.x - a[0]) / (a[1] - a[0]) * (b[1] - b[0])
    uv.y = b[2] + (uv.y - a[2]) / (a[3] - a[2]) * (b[3] - b[2])


def _islands(faces):
    left, out = set(faces), []
    while left:
        stack, isl = [left.pop()], set()
        while stack:
            f = stack.pop()
            isl.add(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g in left:
                        left.remove(g)
                        stack.append(g)
        out.append(isl)
    return out


def _torso_bvh(body):
    """The skin of the trunk only (arms and hands hang close to the hips in the A pose)."""
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bm.transform(body.matrix_world)
    skin = body.vertex_groups["body"].index
    dl = bm.verts.layers.deform.active
    drop = [f for f in bm.faces if abs(f.calc_center_median().x) > 0.19 or not all(skin in v[dl] for v in f.verts)]
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    return tree


def _weights_from(src, mw):
    """A k-d tree of `src`'s vertices (world) and a function giving one vertex's bone weights {name: w}."""
    names = {g.index: g.name for g in src.vertex_groups}
    kd = kdtree.KDTree(len(src.data.vertices))
    for v in src.data.vertices:
        kd.insert(mw @ v.co, v.index)
    kd.balance()

    def weights(p, bones):
        _, i, _ = kd.find(p)
        w = {names[g.group]: g.weight for g in src.data.vertices[i].groups if names[g.group] in bones}
        s = sum(w.values()) or 1.0
        return {k: x / s for k, x in w.items()}

    return weights


def _offset_to(tree, p, n, reach=0.05):
    """How far a surface in `tree` stands off along n from the skin point p (None if nothing within reach)."""
    hit = tree.ray_cast(p + n * reach, -n, reach)
    return None if hit[0] is None else reach - hit[3]


TORSO, SKIRT, STRAPS, SOLES = 0, 1, 2, 3


def _part_geom(bm, tag, which):
    faces = [f for f in bm.faces if f[tag] == which]
    edges = {e for f in faces for e in f.edges}
    verts = {v for f in faces for v in f.verts}
    return faces, edges, verts


def reshape(tunic, body, rig):
    """Skirt, torso and UVs of the v1 tunic; drops the v1 belt."""
    assert tunic.matrix_world.is_identity, "the tunic is expected in the rig's frame"
    skin = _torso_bvh(body)
    bm = bmesh.new()
    bm.from_mesh(tunic.data)
    uvl = bm.loops.layers.uv.active
    tag = bm.faces.layers.int.new("part")  # cuts copy it onto the new faces

    def centre_uv(f):
        return sum((lp[uvl].uv for lp in f.loops), Vector((0, 0))) / len(f.loops)

    bmesh.ops.delete(bm, geom=[f for f in bm.faces if _in(centre_uv(f), OLD_UV["belt"])], context="FACES")
    wool = []
    for f in bm.faces:
        c = centre_uv(f)
        if c.x < 0.75:
            wool.append(f)
        else:
            f[tag] = STRAPS if _in(c, OLD_UV["straps"]) else SOLES
    parts = sorted(_islands(wool), key=lambda s: -sum(f.calc_center_median().z for f in s) / len(s))
    for f in parts[0]:
        f[tag] = TORSO
    for isl in parts[1:]:
        for f in isl:
            f[tag] = SKIRT

    # skirt: hem up, less flare, vertical folds
    faces, edges, verts = _part_geom(bm, tag, SKIRT)
    bmesh.ops.bisect_plane(
        bm,
        geom=list(verts) + list(edges) + faces,
        plane_co=(0, 0, HEM_Z),
        plane_no=(0, 0, -1),
        clear_outer=True,
        dist=1e-5,
    )
    faces, edges, verts = _part_geom(bm, tag, SKIRT)
    for v in verts:
        if v.co.z >= BELT_Z[0]:
            continue
        t_old = min(1.0, (BELT_Z[0] - v.co.z) / (BELT_Z[0] - OLD_HEM_Z))
        k = (1 + NEW_FLARE * t_old) / (1 + OLD_FLARE * t_old)
        v.co.x *= k
        v.co.y = AXIS_Y + (v.co.y - AXIS_Y) * k
        t = min(1.0, (BELT_Z[0] - v.co.z) / (BELT_Z[0] - HEM_Z))
        r = Vector((v.co.x, v.co.y - AXIS_Y, 0))
        if r.length > 1e-6:
            th = math.atan2(v.co.x, v.co.y - AXIS_Y)
            v.co += r.normalized() * FOLD_AMP * t**1.5 * math.sin(FOLDS * th + 0.6 * math.sin(3 * th))

    # slit on his right side: an edge loop on the plane through the body axis, split below SLIT_TOP
    faces, edges, verts = _part_geom(bm, tag, SKIRT)
    res = bmesh.ops.bisect_plane(
        bm, geom=list(verts) + list(edges) + faces, plane_co=(0, AXIS_Y, 0), plane_no=(0, 1, 0), dist=1e-5
    )
    on = [
        e
        for e in res["geom_cut"]
        if isinstance(e, bmesh.types.BMEdge) and all(v.co.x < 0 and v.co.z < SLIT_TOP - 1e-4 for v in e.verts)
    ]
    bmesh.ops.split_edges(bm, edges=on)
    for v in bm.verts:
        if v.co.x < 0 and abs(v.co.y - AXIS_Y) < 1e-4 and HEM_Z - 1e-3 < v.co.z < SLIT_TOP and v.link_faces:
            front = all(f.calc_center_median().y < AXIS_Y for f in v.link_faces)
            back = all(f.calc_center_median().y > AXIS_Y for f in v.link_faces)
            if front != back:
                g = SLIT_GAP / 2 * (SLIT_TOP - v.co.z) / (SLIT_TOP - HEM_Z)
                v.co.y += -g if front else g

    # torso: cut under the rope, cinched at it and bloused above it; the skirt's top drawn in under the rope
    faces, edges, verts = _part_geom(bm, tag, TORSO)
    bmesh.ops.bisect_plane(
        bm,
        geom=list(verts) + list(edges) + faces,
        plane_co=(0, 0, TORSO_CUT),
        plane_no=(0, 0, -1),
        clear_outer=True,
        dist=1e-5,
    )
    bm.normal_update()
    moves = []
    for which in (TORSO, SKIRT):
        for v in _part_geom(bm, tag, which)[2]:
            z = v.co.z
            if which == TORSO and z >= ROPE_Z + BLOUSE_H or which == SKIRT and z < ROPE_Z - 0.05:
                continue
            p, n, _, d = skin.find_nearest(v.co)
            if p is None or d > 0.08:
                continue
            if which == TORSO:
                if z <= ROPE_Z:
                    want = CINCH
                else:
                    want = CINCH + BLOUSE_PUSH * math.sin(math.pi * (z - ROPE_Z) / BLOUSE_H)
                    if z > ROPE_Z + BLOUSE_H / 2:  # blend into v1's stand-off at the top of the ring
                        s = (z - ROPE_Z - BLOUSE_H / 2) / (BLOUSE_H / 2)
                        want = want * (1 - s) + d * s
            else:
                s = min(1.0, (z - (ROPE_Z - 0.05)) / 0.045)
                want = d * (1 - s) + (CINCH - 0.001) * s
            out = v.co - p
            moves.append((v, p + (out.normalized() if out.length > 1e-6 else n) * want))
    for v, co in moves:
        v.co = co

    # UVs: wool squeezed into its region, straps and soles into their new rows
    for f in bm.faces:
        for lp in f.loops:
            if f[tag] in (TORSO, SKIRT):
                _remap(lp[uvl].uv, (0.0, 0.75, 0.0, 1.0), NEW_UV["wool"])
            elif f[tag] == STRAPS:
                _remap(lp[uvl].uv, OLD_UV["straps"], NEW_UV["straps"])
            else:
                _remap(lp[uvl].uv, OLD_UV["soles"], NEW_UV["soles"])
    bm.faces.layers.int.remove(tag)
    bm.normal_update()
    bm.to_mesh(tunic.data)
    bm.free()
    tunic.data.update()


def _catmull(pts, step=0.01):
    pts = [Vector(p) for p in pts]
    out = []
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = pts[max(0, i - 1)], pts[i], pts[i + 1], pts[min(len(pts) - 1, i + 2)]
        n = max(2, int((p2 - p1).length / step))
        for k in range(n):
            t = k / n
            out.append(
                0.5
                * (
                    2 * p1
                    + (-p0 + p2) * t
                    + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                    + (-p0 + 3 * p1 - 3 * p2 + p3) * t**3
                )
            )
    out.append(pts[-1])
    return out


class _Part:
    """Geometry for one new piece: verts with bone weights, faces with UVs (0..1 inside the piece's region).
    `outward`: faces are turned to point away from the piece's own inside (closed pieces); otherwise as wound."""

    def __init__(self, region, outward=True):
        self.region, self.outward, self.co, self.faces, self.w = region, outward, [], [], []

    def vert(self, p, w):
        self.co.append(Vector(p))
        self.w.append(w)
        return len(self.co) - 1

    def face(self, idx, uvs):
        self.faces.append((idx, uvs))


def _frame(t):
    up = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
    nx = t.cross(up).normalized()
    return nx, t.cross(nx)


def _tube(part, path, radius, sides, weights_at):
    """A tube along `path` (closed when path[0] == path[-1]); UV u runs along it, v round it."""
    closed = (path[0] - path[-1]).length < 1e-6
    pts = path[:-1] if closed else path
    n = len(pts)
    rings = []
    for i, c in enumerate(pts):
        a = pts[(i + 1) % n] if closed or i + 1 < n else c
        b = pts[i - 1] if closed or i > 0 else c
        nx, ny = _frame((a - b).normalized())
        w = weights_at(c)
        rings.append(
            [
                part.vert(
                    c + radius * (math.cos(2 * math.pi * k / sides) * nx + math.sin(2 * math.pi * k / sides) * ny), w
                )
                for k in range(sides)
            ]
        )
    steps = n if closed else n - 1
    for i in range(steps):
        r0, r1 = rings[i], rings[(i + 1) % n]
        u0, u1 = i / steps, (i + 1) / steps
        for k in range(sides):
            k1 = (k + 1) % sides
            part.face(
                (r0[k], r1[k], r1[k1], r0[k1]),
                [(u0, k / sides), (u1, k / sides), (u1, (k + 1) / sides), (u0, (k + 1) / sides)],
            )


def _sphere(part, point_at, weights_at, segs, rings):
    """A UV sphere with single pole vertices; point_at(d) places the unit direction d."""
    top = part.vert(point_at(Vector((0, 0, 1))), None)
    bot = part.vert(point_at(Vector((0, 0, -1))), None)
    grid = []
    for j in range(1, rings):
        phi = math.pi * j / rings
        grid.append(
            [
                part.vert(
                    point_at(
                        Vector(
                            (
                                math.sin(phi) * math.cos(2 * math.pi * i / segs),
                                math.sin(phi) * math.sin(2 * math.pi * i / segs),
                                math.cos(phi),
                            )
                        )
                    ),
                    None,
                )
                for i in range(segs)
            ]
        )
    for i in range(len(part.w)):
        if part.w[i] is None:
            part.w[i] = weights_at(part.co[i])
    for i in range(segs):
        i1 = (i + 1) % segs
        u0, u1 = i / segs, (i + 1) / segs
        part.face((top, grid[0][i], grid[0][i1]), [((u0 + u1) / 2, 1.0), (u0, 1 - 1 / rings), (u1, 1 - 1 / rings)])
        part.face((bot, grid[-1][i1], grid[-1][i]), [((u0 + u1) / 2, 0.0), (u1, 1 / rings), (u0, 1 / rings)])
        for j in range(rings - 2):
            v0, v1 = 1 - (j + 1) / rings, 1 - (j + 2) / rings
            part.face(
                (grid[j][i], grid[j + 1][i], grid[j + 1][i1], grid[j][i1]), [(u0, v0), (u0, v1), (u1, v1), (u1, v0)]
            )


def _blob(centre, half, weights_at, region, seed):
    """A small lumpy ellipsoid (a knot), as its own piece."""
    rnd = random.Random(seed)
    part = _Part(region)
    _sphere(
        part,
        lambda d: Vector(centre) + Vector((d.x * half[0], d.y * half[1], d.z * half[2])) * (1 + 0.12 * rnd.random()),
        weights_at,
        10,
        6,
    )
    return part


def rope(tunic, body, rig):
    """The rope round the waist, its knot at his front left and its two ends."""
    skin = _torso_bvh(body)
    cloth = BVHTree.FromObject(tunic, bpy.context.evaluated_depsgraph_get(), deform=False)
    bones = {b.name for b in rig.data.bones}
    from_tunic = _weights_from(tunic, tunic.matrix_world)

    def w(c):
        return from_tunic(c, bones)

    axis = Vector((0, AXIS_Y, ROPE_Z))
    ring = []
    for i in range(ROPE_SEG):
        th = 2 * math.pi * i / ROPE_SEG
        d = Vector((math.sin(th), -math.cos(th), 0))  # i = 0 at his front
        p, n, _, _ = skin.ray_cast(axis + d * 0.4, -d, 0.4)
        off = max(_offset_to(cloth, p, n) or 0.0, CINCH) + ROPE_R + 0.001
        ring.append(p + n * off)
    ring.append(ring[0])
    loop = _Part(NEW_UV["rope"])
    _tube(loop, ring, ROPE_R, 6, w)
    kd = Vector((0.6, -0.8, 0)).normalized()  # his front left
    knot = max(ring[:-1], key=lambda c: (c - axis).normalized().dot(kd))
    out = Vector((knot.x, knot.y - AXIS_Y, 0)).normalized()
    pieces = [loop, _blob(knot + out * 0.006, (0.017, 0.017, 0.014), w, NEW_UV["rope"], 3)]
    for side in (-1, 1):
        tail = _Part(NEW_UV["rope"])
        start = knot + out * 0.008 + Vector((0, 0, -0.01))
        across = Vector((out.y, -out.x, 0)) * side
        path = [
            start
            + across * 0.006 * (s / 6) ** 0.5
            + out * 0.012 * math.sin(math.pi * s / 12)
            + Vector((0, 0, -TAIL_LEN * s / 6))
            for s in range(7)
        ]
        _tube(tail, path, ROPE_R * 0.9, 5, w)
        pieces.append(tail)
    return pieces


def _smooth(xs, k=3):
    return [sum(xs[max(0, i - k) : i + k + 1]) / len(xs[max(0, i - k) : i + k + 1]) for i in range(len(xs))]


def bands_and_knot(tunic, body, rig):
    skin = _torso_bvh(body)
    cloth = BVHTree.FromObject(tunic, bpy.context.evaluated_depsgraph_get(), deform=False)
    bones = {b.name for b in rig.data.bones}
    from_body = _weights_from(body, body.matrix_world)
    pieces = []
    for band in (BAND_A, BAND_B):
        part = _Part(NEW_UV["bands"], outward=False)
        path = _catmull(band)
        hits = [skin.find_nearest(c) for c in path]
        offs = _smooth([(_offset_to(cloth, p, n) or 0.0) + 0.004 for p, n, _, _ in hits])
        strip = []
        for i, ((p, n, _, _), off) in enumerate(zip(hits, offs)):
            t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
            side = n.cross(t).normalized()
            wt = from_body(p, bones)
            c = p + n * off
            strip.append((part.vert(c + side * BAND_HALF_W, wt), part.vert(c - side * BAND_HALF_W, wt)))
        last = len(strip) - 1
        for i in range(last):
            u0, u1 = i / last, (i + 1) / last
            # wound so the face normal points away from the skin
            part.face(
                (strip[i][1], strip[i + 1][1], strip[i + 1][0], strip[i][0]), [(u0, 0), (u1, 0), (u1, 1), (u0, 1)]
            )
        pieces.append(part)
    p, n, _, _ = skin.find_nearest(Vector(KNOT_CHEST))
    off = (_offset_to(cloth, p, n) or 0.0) + 0.012
    pieces.append(_blob(p + n * off, (0.024, 0.016, 0.02), lambda c: from_body(c, bones), NEW_UV["bands"], 5))
    return pieces


def bundle(body, rig):
    """The bundle on his back and its bone."""
    skin = _torso_bvh(body)

    def back_y(x, z):
        xc = max(-0.16, min(0.16, x))
        hit = skin.ray_cast(Vector((xc, 0.6, z)), Vector((0, -1, 0)), 1.0)
        y = hit[0].y if hit[0] is not None else 0.12
        return y - 0.35 * max(0.0, abs(x) - 0.16)

    yb = back_y(0.0, BUNDLE_C_Z)
    centre = Vector((0.0, yb + 0.014 + BUNDLE_HALF[1], BUNDLE_C_Z))
    rnd = random.Random(7)
    # the things inside push the cloth out in a few soft lumps
    lumps = [(Vector([rnd.uniform(-1, 1) for _ in range(3)]).normalized(), rnd.uniform(0.6, 1.0)) for _ in range(7)]

    def place(d):
        e = [math.copysign(abs(c) ** 0.75, c) for c in d]  # boxier than an ellipsoid: a cloth bundle
        p = centre + Vector((e[0] * BUNDLE_HALF[0], e[1] * BUNDLE_HALF[1], e[2] * BUNDLE_HALF[2]))
        p.x *= 1 + 0.08 * max(0.0, -e[2])  # sags wider at the bottom
        bump = sum(a * math.exp((d.dot(c) - 1) / 0.08) for c, a in lumps)
        p += (p - centre).normalized() * (0.024 * bump + 0.004 * (rnd.random() - 0.5))
        p.y = max(p.y, back_y(p.x, p.z) + 0.014)  # pressed flat against his back
        return p

    part = _Part(NEW_UV["bundle"])
    _sphere(part, place, lambda c: {"bundle": 1.0}, 24, 12)
    # its bone: from the middle of the side against the back, upwards, under spine_03
    vl = bpy.context.view_layer
    was = vl.objects.active
    if was is not None and was.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    rig.hide_set(False)
    vl.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    eb = rig.data.edit_bones.get("bundle") or rig.data.edit_bones.new("bundle")
    eb.head = (0.0, yb + 0.02, BUNDLE_C_Z + 0.05)
    eb.tail = (0.0, yb + 0.02, BUNDLE_C_Z + 0.15)
    eb.parent = rig.data.edit_bones["spine_03"]
    eb.use_connect = False
    eb.use_deform = True
    bpy.ops.object.mode_set(mode="OBJECT")
    vl.objects.active = was
    return [part]


def _add(tunic, parts):
    """Append the pieces' geometry, weights and UVs to the tunic."""
    me = tunic.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv.active
    dl = bm.verts.layers.deform.verify()
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
        u0, u1, v0, v1 = u0 + UV_MARGIN, u1 - UV_MARGIN, v0 + UV_MARGIN, v1 - UV_MARGIN
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
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()


def build(tunic_name="Tunic", body_name="Body", rig_name="Rig"):
    tunic, body, rig = (bpy.data.objects[n] for n in (tunic_name, body_name, rig_name))
    for o in (tunic, body):
        o.data.update()
    reshape(tunic, body, rig)
    parts = rope(tunic, body, rig) + bands_and_knot(tunic, body, rig) + bundle(body, rig)
    _add(tunic, parts)
    return {"tunic_tris": sum(len(p.vertices) - 2 for p in tunic.data.polygons), "bones": len(rig.data.bones)}
