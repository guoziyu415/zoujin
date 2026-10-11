"""The execution ground's crowd (F-4 range 1): three low bodies from MPFB 2, one per costume, written as one binary
pack the runtime (apps/web/src/three/crowd/pack.ts) instances.

  BLENDER_USER_RESOURCES=<dir with extensions/user_default/mpfb> python build_crowd.py -- <out_dir> [preview.png]

build.sh lays MPFB out as a local extension at a pinned commit. Only MPFB's own data is used (the base mesh, the
macro targets, the game_engine rig and its weights: CC0, LICENSE.ASSETS.md); no skins, no asset packs. Each body:
the MakeHuman base mesh with the macro details below and the game_engine rig; the costume cut from MPFB's own helper
geometry (the tights for the upper body, the skirt for the robe) and the body under it cut away; decimated to about
TARGET_TRIS; then the outer pieces copied from it and pushed outwards (short hair; the himation, the veil or the felt
cap), their edges cut straight along planes; the arms brought down from MPFB's A pose and that made the rest pose (the
crowd stands). Four parts per vertex (skin, cloth, the outer piece, hair) that the runtime colours from the palette
per instance. The third finger joints are merged into the second (card: one level fewer). Everything is fixed: two
runs write the same bytes.

Coordinates in the pack: three.js (Y up, the person facing +Z, their left at +X), metres.
"""

import hashlib
import importlib
import json
import math
import os
import struct
import sys
import tomllib

import bpy  # first: bmesh, addon_utils and mathutils only import once bpy has  # isort: skip

import addon_utils  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402

TARGET_TRIS = 3000
RACE = {"caucasian": 0.6, "african": 0.2, "asian": 0.2}  # the palette tints the skin per instance on top of this
# (costume, macro details, robe hem height in m, sleeves to the wrist)
BODIES = [
    ("mantle", {"gender": 1.0, "age": 0.55, "muscle": 0.5, "weight": 0.5, "height": 0.5}, 0.16, True),
    ("veil", {"gender": 0.0, "age": 0.5, "muscle": 0.45, "weight": 0.52, "height": 0.42}, 0.06, True),
    ("worker", {"gender": 1.0, "age": 0.6, "muscle": 0.68, "weight": 0.58, "height": 0.45}, 0.5, False),
]
SKIN, CLOTH, OUTER, HAIR = 0, 1, 2, 3
ARMS_DOWN = math.radians(-38)  # MPFB's A pose has the arms ~48° out; the crowd's hang ~10° from the body
FOREARM_BEND = math.radians(12)
# a fist: each finger bone bent about its own X axis (MPFB's game_engine rig: +X closes the hand on both sides)
FIST = {"01": math.radians(80), "02": math.radians(95)}
THUMB_FIST = math.radians(35)
FOLDS, FOLD_DEPTH = 7, 0.035  # the himation's folds round the body, and their depth at the hem
PILOS_HEIGHT = 0.045  # how far the worker's cap rises above the crown
HAIR_SLOPE = 0.93  # the hairline drops this much per metre towards the back
MANTLE_EDGE, MANTLE_SLOPE = (-0.2, 1.05), 1.25  # the himation's edge: (x, z) at the right hip, rising to the left
MANTLE_HEM, MANTLE_HEM_SLOPE = 0.5, 0.45  # its hem at x = 0, lower on the right (z falls 0.45 per metre towards -x)
NECKLINE, NECK_TILT = 0.02, 0.35  # the clothes' neckline: this far under the neck joint at the side, lower in front
NECK_SKIN = {"spine_03", "clavicle_l", "clavicle_r", "neck_01"}
UPPER = {"pelvis", "spine_01", "spine_02", "spine_03", "clavicle_l", "clavicle_r", "upperarm_l", "upperarm_r"}
FOREARM = {"lowerarm_l", "lowerarm_r"}
LEGS = {"thigh_l", "thigh_r", "calf_l", "calf_r"}
ARMS = {f"{b}_{s}" for b in ("upperarm", "lowerarm", "hand") for s in "lr"}
BONE_NAMES = set()  # the game_engine rig's (main() reads them from MPFB)


def mpfb(name):
    return importlib.import_module("bl_ext.user_default.mpfb.services." + name)


def make_human(macro):
    HS = mpfb("humanservice").HumanService
    TS = mpfb("targetservice").TargetService
    details = TS.get_default_macro_info_dict()
    details.update(macro)
    details["race"] = dict(RACE)
    base = HS.create_human(macro_detail_dict=details)
    rig = HS.add_builtin_rig(base, "game_engine")
    for m in list(base.modifiers):
        if m.type == "MASK":
            base.modifiers.remove(m)
    bpy.context.view_layer.objects.active = base
    base.select_set(True)
    if base.data.shape_keys:
        bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
    return base, rig


def dominant(v, names):
    best, w = None, 0.0
    for g in v.groups:
        n = names.get(g.group)
        if n is not None and g.weight > w:
            best, w = n, g.weight
    return best


def in_group(v, gi):
    return any(g.group == gi and g.weight > 0.5 for g in v.groups)


def build_costume(base, costume, hem, sleeves, neck):
    """One mesh: skin where it shows, the costume from the helpers, the outer piece; material index = part. The
    clothes' top edge is cut straight along the neckline (a plane through `neck`, the neck joint's height, lower in
    front); the skin under it is kept a little way down so the cut edge never shows a gap."""
    me = base.data
    names = {g.index: g.name for g in base.vertex_groups if g.name in BONE_NAMES}
    body_g = base.vertex_groups["body"].index
    tights_g = base.vertex_groups["helper-tights"].index
    skirt_g = base.vertex_groups["helper-skirt"].index
    z = [v.co.z for v in me.vertices]
    top = max(z[i] for i, v in enumerate(me.vertices) if in_group(v, body_g))

    covered = set(UPPER) | (FOREARM if sleeves else set())
    keep_skin, keep_cloth = set(), set()
    for v in me.vertices:
        d = dominant(v, names)
        if in_group(v, body_g):
            hidden = d in covered or (d in LEGS and v.co.z > hem + 0.04)
            if costume == "worker" and d in LEGS:
                hidden = v.co.z > hem + 0.04  # bare calves below the knee-length tunic
            if hidden and d in NECK_SKIN and v.co.z > neck - 0.14:
                hidden = False  # under the neckline
            if not hidden:
                keep_skin.add(v.index)
        elif in_group(v, tights_g):
            if d in covered and v.co.z > 0.8:
                keep_cloth.add(v.index)
        elif in_group(v, skirt_g):
            if v.co.z >= hem:
                keep_cloth.add(v.index)

    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    for f in bm.faces:
        ids = {v.index for v in f.verts}
        f.material_index = SKIN if ids <= keep_skin else CLOTH if ids <= keep_cloth else 9
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index == 9], context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    # the neckline: the clothes cut along a plane, not along their faces' steps
    z0, no = neck - NECKLINE, Vector((0, -NECK_TILT, 1)).normalized()
    cloth = [f for f in bm.faces if f.material_index == CLOTH]
    geom = bmesh.ops.bisect_plane(bm, geom=cloth + list({e for f in cloth for e in f.edges})
                                  + list({v for f in cloth for v in f.verts}),
                                  dist=1e-5, plane_co=Vector((0, 0, z0)), plane_no=no)["geom"]
    above = [g for g in geom if isinstance(g, bmesh.types.BMFace) and g.material_index == CLOTH
             and no.dot(g.calc_center_median() - Vector((0, 0, z0))) > 0]
    bmesh.ops.delete(bm, geom=above, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")

    out = bpy.data.meshes.new(f"crowd-{costume}")
    bm.to_mesh(out)
    bm.free()
    obj = bpy.data.objects.new(f"crowd-{costume}", out)
    bpy.context.collection.objects.link(obj)
    for g in base.vertex_groups:
        obj.vertex_groups.new(name=g.name)
    for _ in range(4):
        out.materials.append(None)
    return obj, top


def add_pieces(obj, costume, top, dry=False):
    """The outer pieces: copies of a region pushed out along its normals (the hair first, the cap goes over it).
    dry: only count the triangles they would add (decimate() leaves room for them; the copies are made after it,
    so they lie exactly over what they copy)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    names = {g.index: g.name for g in obj.vertex_groups if g.name in BONE_NAMES}
    dl = bm.verts.layers.deform.active
    ears = obj.vertex_groups["ears"].index

    def bone_of(f):  # the face's dominant bone
        tot = {}
        for v in f.verts:
            for gi, w in v[dl].items():
                if gi in names:
                    tot[gi] = tot.get(gi, 0.0) + w
        return names[max(tot, key=tot.get)] if tot else None

    def is_ear(f):
        return any(v[dl].get(ears, 0.0) > 0.5 for v in f.verts)

    def grow(pick, planes, keep, push, part, shape=None):
        """Copy the faces `pick` takes, split the copy along `planes` (a point and a normal each) and keep the pieces
        whose centre `keep` takes, so its edges run straight along the planes rather than along the faces' steps;
        push it out along its normals by `push`."""
        region = [f for f in bm.faces if f.material_index != OUTER and pick(f, f.calc_center_median(), bone_of(f))]
        if dry:
            counted.append(sum(len(f.verts) - 2 for f in region))  # a little more than is kept
            return
        geom = bmesh.ops.duplicate(bm, geom=region)["geom"]
        for co, no in planes:
            geom = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=Vector(co),
                                          plane_no=Vector(no).normalized())["geom"]
        faces = [g for g in geom if isinstance(g, bmesh.types.BMFace)]
        bmesh.ops.delete(bm, geom=[f for f in faces if not keep(f.calc_center_median())], context="FACES")
        faces = [f for f in faces if f.is_valid]
        bm.normal_update()
        verts = list({v for f in faces for v in f.verts})
        for v in verts:
            v.co += v.normal * push
        if shape:
            start = {v: (v.co.copy(), v.normal.copy()) for v in verts}
            shape(verts)
            for v, (co, no) in start.items():  # never back in under where it was pushed out to (the body would show)
                d = (v.co - co).dot(no)
                if d < 0:
                    v.co -= no * d
            # and cut along the planes again: the shaping moved the edges off them
            geom = faces + list({e for f in faces for e in f.edges}) + verts
            for co, no in planes:
                geom = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=Vector(co),
                                              plane_no=Vector(no).normalized())["geom"]
            faces = [g for g in geom if isinstance(g, bmesh.types.BMFace)]
            bmesh.ops.delete(bm, geom=[f for f in faces if not keep(f.calc_center_median())], context="FACES")
            faces = [f for f in faces if f.is_valid]
            bmesh.ops.delete(bm, geom=[v for v in verts if v.is_valid and not v.link_faces], context="VERTS")
        for f in faces:
            f.material_index = part

    def head(f, bone):
        return f.material_index == SKIN and bone == "head" and not is_ear(f)

    def smooth(verts, times, factor=0.5):
        """Laplacian smoothing; the edge is smoothed along itself, so it stays a clean line."""
        inner = [v for v in verts if not v.is_boundary]
        rim = {v: [e.other_vert(v) for e in v.link_edges if e.is_boundary] for v in verts if v.is_boundary}
        for _ in range(times):
            bmesh.ops.smooth_vert(bm, verts=inner, factor=factor, use_axis_x=True, use_axis_y=True, use_axis_z=True)
            moved = {v: sum((n.co for n in ns), Vector()) / len(ns) for v, ns in rim.items() if len(ns) == 2}
            for v, to in moved.items():
                v.co += (to - v.co) * factor

    def drape(verts):
        """The himation hangs: no body under it (smoothed), from the hips straight down rather than in round the
        legs, a few big folds that deepen towards the hem."""
        smooth(verts, 6)
        cx = sum(v.co.x for v in verts) / len(verts)
        cy = sum(v.co.y for v in verts) / len(verts)
        hips = 0.95
        reach = {}  # the widest it gets at the hips, by direction
        for v in verts:
            if abs(v.co.z - hips) < 0.06:
                a = round(math.atan2(v.co.y - cy, v.co.x - cx) / (math.pi / 12))
                reach[a] = max(reach.get(a, 0.0), math.hypot(v.co.x - cx, v.co.y - cy))
        def reach_at(a):  # between the bins, and nothing where the himation doesn't reach the hips
            f = a / (math.pi / 12)
            lo, hi = math.floor(f), math.floor(f) + 1
            if lo not in reach or hi not in reach:
                return 0.0
            return reach[lo] + (reach[hi] - reach[lo]) * (f - lo)

        for v in verts:
            dx, dy = v.co.x - cx, v.co.y - cy
            r, a = math.hypot(dx, dy), math.atan2(dy, dx)
            if r < 1e-6:
                continue
            if v.co.z < hips:
                fall = min(1.0, (hips - v.co.z) / 0.25)  # eased in under the hips
                r = max(r, r + (0.95 * reach_at(a) - r) * fall)
            v.co.x, v.co.y = cx + r * math.cos(a), cy + r * math.sin(a)
        smooth(verts, 1, 0.3)
        for v in verts:  # the folds last, so the smoothing doesn't take them out
            a = math.atan2(v.co.y - cy, v.co.x - cx)
            depth = FOLD_DEPTH * min(1.0, max(0.0, (hips + 0.25 - v.co.z) / (hips + 0.25 - MANTLE_HEM)))
            v.co.x += depth * math.sin(FOLDS * a + 0.6) * math.cos(a)
            v.co.y += depth * math.sin(FOLDS * a + 0.6) * math.sin(a)

    def hood(top, chin):
        def shape(verts):
            """The veil stands off the head and falls to the shoulders: smoothed (no ears or nape under it), pushed out
            a little more over the skull, and the back and sides below the ears filled out to a straight fall."""
            smooth(verts, 8)
            cy = sum(v.co.y for v in verts) / len(verts)
            ear = top - 0.13
            head = [v for v in verts if v.co.z > ear]
            back = max(v.co.y for v in head)
            side = max(abs(v.co.x) for v in head)
            for v in verts:
                if v.co.z > ear:
                    v.co.x *= 1.06
                    v.co.y = cy + (v.co.y - cy) * 1.06
                    v.co.z += 0.012
                else:
                    drop = ear - v.co.z
                    if v.co.y > cy:
                        v.co.y = max(v.co.y, back - 0.1 * drop)
                    if v.co.y > cy - 0.02:
                        v.co.x = math.copysign(max(abs(v.co.x), side + 0.5 * drop), v.co.x)
            smooth(verts, 2, 0.4)
        return shape

    def pilos(top):
        def shape(verts):
            """The felt cap rises to a blunt point (a pilos)."""
            smooth(verts, 2)
            cx = sum(v.co.x for v in verts) / len(verts)
            cy = sum(v.co.y for v in verts) / len(verts)
            reach = max(math.hypot(v.co.x - cx, v.co.y - cy) for v in verts)
            for v in verts:
                k = 1 - math.hypot(v.co.x - cx, v.co.y - cy) / reach
                v.co.z += PILOS_HEIGHT * max(0.0, k) ** 1.4
        return shape

    counted = []
    bm.normal_update()
    if costume != "veil":
        # short hair: from the forehead (6 cm under the crown) sloping down over the ears to the nape
        line = (0, -0.1, top - 0.06)

        def above(c):
            return c.z - line[2] + HAIR_SLOPE * (c.y - line[1])

        grow(lambda f, c, bone: head(f, bone) and above(c) > -0.03, [(line, (0, HAIR_SLOPE, 1))],
             lambda c: above(c) > 0, 0.008, HAIR)
    if costume == "mantle":
        # the himation: wrapped round from under the right arm over the left shoulder, down to below the knee
        x0, z0 = MANTLE_EDGE

        def below(c):  # how far under the edge
            return z0 + (c.x - x0) * MANTLE_SLOPE - c.z

        def wrapped(f, c, bone):
            on_arm = bone in ARMS and not (bone == "upperarm_l" and c.z > 1.22)
            return f.material_index == CLOTH and not on_arm and c.z > 0.5 and below(c) > -0.08

        def hem_z(c):
            return MANTLE_HEM + MANTLE_HEM_SLOPE * c.x

        grow(wrapped, [((x0, 0, z0), (-MANTLE_SLOPE, 0, 1)), ((0, 0, MANTLE_HEM), (-MANTLE_HEM_SLOPE, 0, 1))],
             lambda c: below(c) > 0 and c.z > hem_z(c), 0.03, OUTER, drape)
    elif costume == "veil":
        # over the head, round the face (open from the forehead, 5 cm under the crown, to under the chin, in front of
        # the ears), down over the shoulders
        brow, chin, cheek, hem = top - 0.05, top - 0.27, -0.075, top - 0.38
        planes = [((0, 0, z), (0, 0, 1)) for z in (brow, chin, hem)] + [((0, cheek, 0), (0, 1, 0))]
        grow(lambda f, c, bone: c.z > hem - 0.04 and bone not in ("lowerarm_l", "lowerarm_r"), planes,
             lambda c: c.z > hem and (c.z > brow or c.z < chin or c.y > cheek), 0.018, OUTER, hood(top, chin))
    else:
        # the worker's low round felt cap on the crown, over the hair
        grow(lambda f, c, bone: head(f, bone) and c.z > top - 0.1, [((0, 0, top - 0.07), (0, 0, 1))],
             lambda c: c.z > top - 0.07, 0.016, OUTER, pilos(top))
    if dry:
        bm.free()
        return sum(counted)
    bm.to_mesh(obj.data)
    bm.free()
    return 0


def stand(rig, obj):
    """Bring the arms down, bend the elbows a little, and make that the rest pose of rig and mesh."""
    mod = obj.modifiers.new("rig", "ARMATURE")
    mod.object = rig
    obj.parent = rig
    pb = rig.pose.bones
    world = rig.matrix_world.to_3x3()
    for side, s in (("l", 1), ("r", -1)):
        for bone, axis, angle in ((f"upperarm_{side}", Vector((0, 1, 0)), -s * ARMS_DOWN),
                                  (f"lowerarm_{side}", Vector((1, 0, 0)), FOREARM_BEND)):
            p = pb[bone]
            p.rotation_mode = "QUATERNION"
            local = (world @ p.bone.matrix_local.to_3x3()).inverted() @ axis  # the world axis in the bone's frame
            p.rotation_quaternion = Quaternion(local, angle)
    bpy.context.view_layer.update()
    bpy.context.view_layer.objects.active = obj
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier="rig")
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def merge_third_joints(obj):
    for g in list(obj.vertex_groups):
        if g.name.endswith(("_03_l", "_03_r")) and not g.name.startswith("spine"):
            parent = obj.vertex_groups.get(g.name.replace("_03_", "_02_"))
            if parent is None:
                continue
            for v in obj.data.vertices:
                for e in v.groups:
                    if e.group == g.index and e.weight > 0:
                        parent.add([v.index], e.weight, "ADD")
            obj.vertex_groups.remove(g)


def decimate(obj, extra):
    """To about TARGET_TRIS once the outer pieces (`extra` triangles at full detail) are copied on."""
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    ratio = TARGET_TRIS / (tris + extra)
    if ratio >= 1:
        return
    mod = obj.modifiers.new("dec", "DECIMATE")
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="dec")


def to_three(v):
    return (v.x, v.z, -v.y)


def fist(rig, skeleton):
    """Each finger bone's bend at a fist: its index, its X axis at rest (three's axes) and the angle."""
    out = []
    for i, b in enumerate(skeleton):
        kind, *rest = b["name"].split("_")
        if kind not in ("index", "middle", "ring", "pinky", "thumb"):
            continue
        x = (rig.matrix_world.to_3x3() @ rig.data.bones[b["name"]].matrix_local.to_3x3()).col[0].normalized()
        angle = THUMB_FIST if kind == "thumb" else FIST[rest[0]]
        out.append([i, *(round(c, 4) for c in to_three(x)), round(angle, 4)])
    return out


def export(built, out_dir):
    rig = built[0][1]
    bones = [b for b in rig.data.bones if not (b.name.endswith(("_03_l", "_03_r")) and "spine" not in b.name)]
    bones = [b for b in bones if b.name != "Root"]
    index = {b.name: i for i, b in enumerate(bones)}
    skeleton = []
    for b in bones:
        p = b.parent
        while p is not None and p.name not in index:
            p = p.parent
        skeleton.append({"name": b.name, "parent": index[p.name] if p else -1})
    blob = bytearray()
    costumes = {}
    for obj, rig in built:
        me = obj.data
        me.calc_loop_triangles()
        names = {g.index: g.name for g in obj.vertex_groups}
        verts, idx, remap = [], [], {}
        for tri in me.loop_triangles:
            part = me.polygons[tri.polygon_index].material_index
            for vi in tri.vertices:
                key = (vi, part)
                if key not in remap:
                    v = me.vertices[vi]
                    ws = sorted(((g.weight, index[names[g.group]]) for g in v.groups
                                 if names.get(g.group) in index and g.weight > 0.002), reverse=True)[:4]
                    total = sum(w for w, _ in ws) or 1.0
                    q = [round(255 * w / total) for w, _ in ws]
                    if q:
                        q[0] += 255 - sum(q)
                    ws = [(q[i], ws[i][1]) for i in range(len(ws))] + [(0, 0)] * (4 - len(ws))
                    remap[key] = len(verts)
                    verts.append((to_three(v.co), to_three(v.normal), ws, part))
                idx.append(remap[key])
        off = len(blob)
        for p, *_ in verts:
            blob += struct.pack("<3f", *p)
        for _, n, *_ in verts:
            blob += struct.pack("<3h", *(max(-32767, min(32767, round(c * 32767))) for c in n))
            blob += b"\0\0"
        for *_, ws, _ in verts:
            blob += bytes(i for _, i in ws)
        for *_, ws, _ in verts:
            blob += bytes(w for w, _ in ws)
        for *_, part in verts:
            blob += bytes([part])
        while len(blob) % 4:
            blob += b"\0"
        ioff = len(blob)
        blob += struct.pack(f"<{len(idx)}H", *idx)
        while len(blob) % 4:
            blob += b"\0"
        lo = [min(v[0][k] for v in verts) for k in range(3)]
        hi = [max(v[0][k] for v in verts) for k in range(3)]
        costumes[obj.name.removeprefix("crowd-")] = {
            "vertices": len(verts), "offset": off, "indices": len(idx), "indexOffset": ioff,
            "triangles": len(idx) // 3, "min": [round(c, 4) for c in lo], "max": [round(c, 4) for c in hi],
            # each body's own joints (the rest pose: arms down), in the order of "bones"
            "joints": [[round(c, 5) for c in to_three(rig.matrix_world @ rig.data.bones[b["name"]].head_local)]
                       for b in skeleton],
            # the fingers' bend at a fist: bone, axis (at rest, three's axes), angle
            "fist": fist(rig, skeleton),
        }
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "crowd.bin"), "wb") as f:
        f.write(blob)
    root = os.path.join(os.path.dirname(mpfb("locationservice").__file__), "..")
    with open(os.path.join(root, "blender_manifest.toml"), "rb") as f:
        version = tomllib.load(f)["version"]
    with open(__file__, "rb") as f:
        script = hashlib.sha256(f.read()).hexdigest()
    manifest = {
        "format": "zoujin-crowd-1",
        "note": "Generated by assets/pipeline/crowd/build.sh; do not edit by hand.",
        "inputs": {"mpfb": {"version": version, "commit": os.environ.get("MPFB_COMMIT") or None},
                   "assets/pipeline/crowd/build_crowd.py": script},
        "frame": "three.js: metres, +Y up, the person facing +Z, their left at +X",
        "layout": "per costume at offset: position f32x3, normal i16x3+pad (snorm), skinIndex u8x4, skinWeight u8x4 "
                  "(sums to 255), part u8 (0 skin, 1 cloth, 2 outer piece, 3 hair); then u16 indices at indexOffset",
        "bones": skeleton,
        "costumes": costumes,
        "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
    }
    with open(os.path.join(out_dir, "crowd.json"), "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return manifest


def preview(objs, path):
    """Two renders: the parts in telling colours from the front, and the palette from behind (the shot's side)."""
    sc = bpy.context.scene
    looks = {
        "front": [(0.8, 0.5, 0.3), (0.2, 0.35, 0.7), (0.7, 0.1, 0.1), (0.1, 0.6, 0.2)],  # skin, cloth, outer, hair
        "back": [(0.32, 0.17, 0.1), (0.51, 0.45, 0.34), (0.11, 0.06, 0.04), (0.03, 0.02, 0.015)],  # #9A6A4C L0 N1
    }
    for k, o in enumerate(objs):
        o.location.x += (k - 1) * 0.9
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 2.9
    sc.camera = cam
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sc.collection.objects.link(sun)
    sun.rotation_euler = (0.7, 0.2, 0.5)
    sc.world = bpy.data.worlds.new("w")
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 8
    sc.render.resolution_x, sc.render.resolution_y = 1000, 800
    for view, colors in looks.items():
        mats = []
        for i, c in enumerate(colors):
            m = bpy.data.materials.new(f"{view}{i}")
            m.use_nodes = True
            m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*c, 1)
            mats.append(m)
        for o in objs:
            for i in range(4):
                o.data.materials[i] = mats[i]
        if view == "front":
            cam.location, cam.rotation_euler = (0.6, -6, 0.95), (math.pi / 2, 0, math.radians(6))
        else:
            cam.location, cam.rotation_euler = (-3.2, 5.1, 0.95), (math.pi / 2, 0, math.radians(180 + 32))
        sc.render.filepath = path if view == "front" else path.replace(".png", f"-{view}.png")
        bpy.ops.render.render(write_still=True)


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out_dir = args[0]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("bl_ext.user_default.mpfb", default_set=True)
    BONE_NAMES.update(json.load(open(os.path.join(
        os.path.dirname(mpfb("locationservice").__file__), "..", "data", "rigs", "standard", "rig.game_engine.json"))))
    built = []
    for costume, macro, hem, sleeves in BODIES:
        base, rig = make_human(macro)
        neck = (rig.matrix_world @ rig.data.bones["neck_01"].head_local).z
        obj, top = build_costume(base, costume, hem, sleeves, neck)
        extra = add_pieces(obj, costume, top, dry=True)
        decimate(obj, extra)
        add_pieces(obj, costume, top)
        stand(rig, obj)
        merge_third_joints(obj)
        bpy.data.objects.remove(base)
        built.append((obj, rig))
    m = export(built, out_dir)
    for c, d in m["costumes"].items():
        print(f"{c}: {d['vertices']} vertices, {d['triangles']} triangles")
    print(f"bones {len(m['bones'])}, {m['bytes']} bytes")
    if len(args) > 1:
        preview([o for o, _ in built], args[1])


if __name__ == "__main__":
    main()
