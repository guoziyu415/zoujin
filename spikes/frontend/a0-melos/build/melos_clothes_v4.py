"""A-0 v4: Melos's tunic per UX's round 4 (ux/reviews/a0-melos.md, round 4, items 1 and 5).

Runs on the output of melos_clothes_v3.py (bpy in the container): <python> melos_clothes_v4.py -- <v3.blend> <out.blend>

- skirt: stands at least SKIRT_GAP off the thighs and takes their bone weights where it is close to them. In the idle
  and talk poses his left thigh came out through the front of the hem (every talk shot of round 4);
- waist: the torso ended just above the rope and the skirt started just under it, with nothing behind the rope. When
  he bends, skin showed through as a dark band. Both edges now run on behind the rope (an inner layer of the same
  cloth), and the ring above the rope blouses out BLOUSE_EXTRA more at its middle (v2's 2 cm read flat);
- a knot of the cloth on his left shoulder, where the exomis is tied (about 5 cm);
- rolled edges at the neck and armhole and at the hem: each free edge turned in, about 5 mm thick, two quads a step;
- `__under_tunic` made again from the geometry: skin whose outward normal meets the cloth within UNDER_REACH, from
  mid-thigh up, not the arms. lod_export.py deletes it in every tier (it only did on the standard tier, and v1's group
  stopped above the thighs).
The new cloth stays in the wool UV region; melos_prep.py unwraps the wool again, these pieces with it.

Frame: MPFB, metres, +Z up, the character faces -Y, his left is +X.
"""

import math
import os
import sys

import bpy  # first: bpy as a module brings bmesh and mathutils with it
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import melos_clothes_v2 as v2  # noqa: E402
import melos_clothes_v3 as v3  # noqa: E402

NEW_UV = v2.NEW_UV
SKIRT_GAP = 0.025  # least stand-off of the skirt from the thighs (m)
SKIRT_TOP = 0.97  # above this the skirt hangs from the hips: neither pushed nor re-weighted
FOLLOW = (0.03, 0.06)  # a skirt vertex this close to the thigh takes all of its weights; this far, none
BLOUSE_EXTRA = 0.012
INNER = {"skirt": (0.035, 0.006), "torso": (-0.03, 0.004)}  # how far each edge runs on behind the rope, its stand-off
SHOULDER_KNOT_S, SHOULDER_KNOT_R = 0.0082, 0.009  # a trefoil about 5 cm across, of a bunched strand of the cloth
ROLL = (0.0025, 0.005, 0.006)  # rolled edge: out past the edge, thickness (in), and how far the turn-in runs back
UNDER_REACH = 0.06
UNDER_ERODE = 2  # vertex rings kept inside the edge of the skin the cloth covers
MID_THIGH_Z = 0.74
ARM_BONES = ("upperarm", "lowerarm", "hand", "thumb", "index", "middle", "ring", "pinky", "clavicle")


def _wool(f, uvl):
    return sum(lp[uvl].uv.x for lp in f.loops) / len(f.loops) < NEW_UV["wool"][1]


def _bones(rig):
    return {b.name for b in rig.data.bones}


def _body_weights(body, rig):
    """Bone weights of each body vertex, normalised, bones only (MPFB also has Left / Right / Mid and `body`)."""
    names = {g.index: g.name for g in body.vertex_groups}
    bones = _bones(rig)
    out = []
    for v in body.data.vertices:
        w = {names[g.group]: g.weight for g in v.groups if names[g.group] in bones and g.weight > 1e-4}
        s = sum(w.values()) or 1.0
        out.append({k: x / s for k, x in w.items()})
    return out


def _set_weights(bm, dl, v, w, gidx, ob):
    v[dl].clear()
    for name, x in w.items():
        if name not in gidx:
            gidx[name] = ob.vertex_groups.new(name=name).index
        v[dl][gidx[name]] = x


def _get_weights(v, dl, names):
    return {names[g]: x for g, x in v[dl].items() if g in names}


def skirt(bm, uvl, dl, tunic, body, rig):
    """Push the skirt off the thighs and hand it their weights where it hangs close to them."""
    tree = v2._torso_bvh(body)
    bw = _body_weights(body, rig)
    bcos = [v.co for v in body.data.vertices]
    names = {g.index: g.name for g in tunic.vertex_groups}
    gidx = {n: i for i, n in names.items()}
    bones = _bones(rig)
    cloth = {v for f in bm.faces if _wool(f, uvl) for v in f.verts}
    lo = v2.HEM_Z - 0.02
    push, follow, near = {}, {}, {}
    for v in cloth:
        if not lo <= v.co.z <= SKIRT_TOP:
            continue
        p, n, fi, d = tree.find_nearest(v.co)
        if p is None:
            continue
        nh = Vector((v.co.x - p.x, v.co.y - p.y, 0.0))
        if nh.length < 1e-6:
            nh = Vector((n.x, n.y, 0.0))
        nh.normalize()
        push[v] = nh * max(0.0, SKIRT_GAP - d)
        top = min(1.0, max(0.0, (SKIRT_TOP - v.co.z) / 0.10))  # weights fade back to v2's towards the hips
        follow[v] = top * min(1.0, max(0.0, (FOLLOW[1] - d) / (FOLLOW[1] - FOLLOW[0])))
        near[v] = p
    # spread each push over its neighbours (never below what the vertex itself needs), so the hem doesn't kink
    for _ in range(4):
        nxt = {}
        for v, a in push.items():
            nb = [push[u] for e in v.link_edges for u in (e.other_vert(v),) if u in push]
            if not nb:
                nxt[v] = a
                continue
            m = sum(nb, Vector()) / len(nb)
            s = a * 0.5 + m * 0.5
            nxt[v] = s if s.length >= a.length else a
        push = nxt
    kd = v2.kdtree.KDTree(len(bcos))
    for i, c in enumerate(bcos):
        kd.insert(c, i)
    kd.balance()
    moved = 0
    for v, a in push.items():
        if a.length > 1e-5:
            v.co += a
            moved += 1
        f = follow[v]
        if f > 0:
            _, i, _ = kd.find(near[v])
            cur = _get_weights(v, dl, names)
            cur = {k: x for k, x in cur.items() if k in bones}
            new = {k: (1 - f) * cur.get(k, 0.0) + f * bw[i].get(k, 0.0) for k in set(cur) | set(bw[i])}
            s = sum(new.values()) or 1.0
            _set_weights(bm, dl, v, {k: x / s for k, x in new.items() if x / s > 1e-3}, gidx, tunic)
    return {"skirt_verts": len(push), "pushed": moved,
            "max_push_cm": round(100 * max(a.length for a in push.values()), 2),
            "followed": sum(1 for x in follow.values() if x > 0.5)}


def _loops(bm, uvl):
    """The cloth's free edges as ordered vertex chains (closed loops), with their mean height."""
    bnd = [e for e in bm.edges if len(e.link_faces) == 1 and _wool(e.link_faces[0], uvl)]
    adj = {}
    for e in bnd:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen, out = set(), []
    for start in adj:
        if start in seen:
            continue
        chain, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = [u for u in adj[cur] if u is not prev and u not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            chain.append(cur)
        out.append(chain)
    return out


def _bridge(bm, ring_a, ring_b, closed):
    """Quads between two rings of the same length (_orient_like turns them the right way afterwards)."""
    new = []
    n = len(ring_a)
    for i in range(n if closed else n - 1):
        j = (i + 1) % n
        try:
            new.append(bm.faces.new((ring_a[i], ring_a[j], ring_b[j], ring_b[i])))
        except ValueError:
            pass
    return new


def _orient_like(bm, new, ref_normal_at):
    """Turn each new face so its normal agrees with the cloth's outward normal nearby."""
    for f in new:
        f.normal_update()
        if f.normal.dot(ref_normal_at(f.calc_center_median())) < 0:
            f.normal_flip()


def _uv_wool(faces, uvl):
    u0, u1, v0, v1 = NEW_UV["wool"]
    for f in faces:
        for lp in f.loops:
            lp[uvl].uv = (u0 + 0.5 * (u1 - u0), v0 + 0.5 * (v1 - v0))  # melos_prep unwraps the wool again


def waist(bm, uvl, dl, tunic, body, rig, cloth_normal_at):
    """Run the torso's lower edge and the skirt's upper edge on behind the rope, and blouse the ring above it."""
    tree = v2._torso_bvh(body)
    loops = _loops(bm, uvl)
    rope_z = v2.ROPE_Z
    near_rope = sorted((c for c in loops if abs(sum(v.co.z for v in c) / len(c) - rope_z) < 0.03),
                       key=lambda c: sum(v.co.z for v in c) / len(c))
    report = {}
    new_faces = []
    for chain, key in zip(near_rope, ("torso", "skirt")):  # the lower one is the torso's edge
        dz, gap = INNER[key]
        ring = []
        for v in chain:
            z = v.co.z + dz
            hit = tree.find_nearest(Vector((v.co.x, v.co.y, z)))
            p, n = hit[0], hit[1]
            nh = Vector((n.x, n.y, 0.0)).normalized() if p is not None else Vector()
            q = Vector((p.x, p.y, z)) + nh * gap if p is not None else Vector((v.co.x, v.co.y, z))
            nv = bm.verts.new(q)
            nv[dl].clear()
            for g, x in v[dl].items():
                nv[dl][g] = x
            ring.append(nv)
        closed = (chain[0].co - chain[-1].co).length < 0.06
        faces = _bridge(bm, chain, ring, closed)
        new_faces += faces
        report[key + "_inner_faces"] = len(faces)
    # the bloused ring above the rope, away from the bands and the bundle (pushing under them would poke through)
    others = BVHTree.FromBMesh(_only(bm, uvl, wool=False))
    lo = rope_z + 0.004
    hi = lo + v2.BLOUSE_H
    inner = {x for f in new_faces for x in f.verts}
    n_blouse = 0
    for v in {v for f in bm.faces if _wool(f, uvl) for v in f.verts} - inner:
        if not lo < v.co.z < hi:
            continue
        t = (v.co.z - lo) / (hi - lo)
        p = tree.find_nearest(v.co)[0]
        if p is None:
            continue
        o = others.find_nearest(v.co)
        clear = o[3] if o[0] is not None else 1.0
        k = min(1.0, max(0.0, (clear - 0.015) / 0.02))
        nh = Vector((v.co.x - p.x, v.co.y - p.y, 0.0)).normalized()
        v.co += nh * BLOUSE_EXTRA * math.sin(math.pi * t) * k
        n_blouse += 1
    report["blouse_verts"] = n_blouse
    _orient_like(bm, new_faces, cloth_normal_at)
    _uv_wool(new_faces, uvl)
    return report


def _only(bm, uvl, wool):
    out = bm.copy()
    ul = out.loops.layers.uv.active
    bmesh.ops.delete(out, geom=[f for f in out.faces if _wool(f, ul) != wool], context="FACES")
    return out


def rolled_edges(bm, uvl, cloth_normal_at):
    """Turn the neck / armhole edge and the hem in: out past the edge and down, then back inside the cloth."""
    # the hem (with the slit) and the neck / armhole edge; not the two edges that now end behind the rope
    loops = [c for c in _loops(bm, uvl) if not 0.9 < sum(v.co.z for v in c) / len(c) < 1.2]
    new = []
    steps = 0
    for chain in loops:
        closed = (chain[0].co - chain[-1].co).length < 0.06
        n = len(chain)
        rim, inner = [], []
        for i, v in enumerate(chain):
            a = chain[(i - 1) % n] if closed or i > 0 else v
            b = chain[(i + 1) % n] if closed or i < n - 1 else v
            t = (b.co - a.co).normalized()
            nrm = cloth_normal_at(v.co)
            # across the edge, away from the cloth: the side of the edge with no face
            face = v.link_faces[0] if v.link_faces else None
            out = t.cross(nrm).normalized()
            if face is not None and (face.calc_center_median() - v.co).dot(out) > 0:
                out = -out
            rim.append(bm.verts.new(v.co + out * ROLL[0] - nrm * ROLL[1] * 0.5))
            inner.append(bm.verts.new(v.co - nrm * ROLL[1] - out * ROLL[2]))
            for nv in (rim[-1], inner[-1]):
                dl = bm.verts.layers.deform.active
                nv[dl].clear()
                for g, x in v[dl].items():
                    nv[dl][g] = x
        f1 = _bridge(bm, chain, rim, closed)
        f2 = _bridge(bm, rim, inner, closed)
        _orient_like(bm, f1, cloth_normal_at)  # the rim faces out and down
        _orient_like(bm, f2, lambda p: -cloth_normal_at(p))  # the turn-in faces the body
        new += f1 + f2
        steps += len(f1)
    _uv_wool(new, uvl)
    return {"rolled_loops": len(loops), "rolled_steps": steps, "rolled_tris": 2 * len(new)}


def shoulder_knot(tunic, rig):
    """The exomis tied on his left shoulder: a small knot of the cloth on top of it, two short ends."""
    mw = tunic.matrix_world
    cloth = [mw @ v.co for v in tunic.data.vertices]
    uv = tunic.data.uv_layers.active.data
    wool_v = set()
    for p in tunic.data.polygons:
        if sum(uv[i].uv[0] for i in p.loop_indices) / p.loop_total < NEW_UV["wool"][1]:
            wool_v.update(p.vertices)
    # on the shoulder, off the neck
    top = max((cloth[i] for i in wool_v if 0.11 < cloth[i].x < 0.17), key=lambda c: c.z)
    centre = top + Vector((0.0, 0.0, 0.012))
    weights = v2._weights_from(tunic, mw)
    bones = _bones(rig)
    part = v2._Part(NEW_UV["wool"])

    def w(p):
        return weights(p, bones)

    v3._knot(part, centre, SHOULDER_KNOT_S, SHOULDER_KNOT_R, Vector((0.25, 0.0, 1.0)), Vector((0, -1, 0)), w,
             v3.BAND_U_M, 30, 6, 7)
    v3._end(part, centre + Vector((0.0, -0.02, -0.004)), Vector((0.1, -1.0, -0.6)), 0.045, 0.011, w, v3.BAND_U_M,
            droop=0.5)
    v3._end(part, centre + Vector((0.0, 0.02, -0.004)), Vector((0.1, 1.0, -0.6)), 0.04, 0.011, w, v3.BAND_U_M,
            droop=0.5)
    return part, [round(x, 3) for x in centre]


def under_tunic(body, tunic, rig):
    """Skin that the cloth covers in the rest pose (from mid-thigh up, not the arms): its outward normal meets the
    cloth from the inside within UNDER_REACH. The group replaces v1's."""
    dg = bpy.context.evaluated_depsgraph_get()
    tree = BVHTree.FromObject(tunic, dg)
    bw = _body_weights(body, rig)
    old = body.vertex_groups.get("__under_tunic")
    if old:
        body.vertex_groups.remove(old)
    g = body.vertex_groups.new(name="__under_tunic")
    mw = body.matrix_world
    nm = mw.to_3x3()
    on = []
    for v in body.data.vertices:
        co = mw @ v.co
        if co.z < MID_THIGH_Z:
            continue
        dom = max(bw[v.index].items(), key=lambda kv: kv[1], default=("", 0))[0]
        if dom.startswith(ARM_BONES) or dom in ("neck_01", "head"):
            continue
        n = (nm @ v.normal).normalized()
        loc, hn, _, _ = tree.ray_cast(co + n * 0.0005, n, UNDER_REACH)
        if loc is not None and hn.dot(n) > 0:
            on.append(v.index)
    # two rings of skin kept inside the cover's edge: under the neckline and the armholes the cut showed as a row of
    # black teeth (looking under the cloth's edge into the body); the skin there stays under the rolled edge
    me = body.data
    nbr = {i: set() for i in range(len(me.vertices))}
    for e in me.edges:
        a, b = e.vertices
        nbr[a].add(b)
        nbr[b].add(a)
    keep = set(on)
    for _ in range(UNDER_ERODE):
        keep = {i for i in keep if nbr[i] <= keep}
    on = sorted(keep)
    g.add(on, 1.0, "REPLACE")
    # only faces with all their corners covered go (lod_export deletes the group's vertices): drop the lone ones at
    # the edge of the cover so the cut follows whole faces
    full = set()
    for p in me.polygons:
        if all(i in keep for i in p.vertices):
            full.update(p.vertices)
    lone = sorted(keep - full)
    if lone:
        g.remove(lone)
    return {"under_tunic_verts": len(full)}


def build(tunic_name="Tunic", body_name="Body", rig_name="Rig"):
    tunic, body, rig = (bpy.data.objects[n] for n in (tunic_name, body_name, rig_name))
    for o in (tunic, body):
        o.data.update()
    report = {}
    me = tunic.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv.active
    dl = bm.verts.layers.deform.verify()
    report |= skirt(bm, uvl, dl, tunic, body, rig)
    bm.normal_update()
    cloth_only = _only(bm, uvl, wool=True)
    cloth_only.normal_update()
    ctree = BVHTree.FromBMesh(cloth_only)

    def cloth_normal_at(p):
        hit = ctree.find_nearest(p)
        return hit[1] if hit[0] is not None else Vector((0, 0, 1))

    report |= waist(bm, uvl, dl, tunic, body, rig, cloth_normal_at)
    report |= rolled_edges(bm, uvl, cloth_normal_at)
    cloth_only.free()
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()
    part, report["shoulder_knot"] = shoulder_knot(tunic, rig)
    v2._add(tunic, [part])
    report |= under_tunic(body, tunic, rig)
    report["tunic_tris"] = sum(len(p.vertices) - 2 for p in tunic.data.polygons)
    return report


if __name__ == "__main__" and "--" in sys.argv:
    src, dst = sys.argv[-2], sys.argv[-1]
    bpy.ops.wm.open_mainfile(filepath=src)
    print(build())
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(dst), compress=True)
