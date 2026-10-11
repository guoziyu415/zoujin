"""The other characters (F-16) from Melos's MPFB build: one .blend each, ready for lod_export.py.

  BLENDER_USER_RESOURCES=<dir with extensions/user_default/mpfb> python -I build_cast.py -- <melos.blend> <id> <out.blend> [variant]

Melos's file (A-0, MPFB 2 on the Mac) carries the parts every character shares: the skin with its 52 ARKit and 15
viseme shape keys, the eyes, brows, lashes, teeth and tongue, and their CC0 MPFB textures, packed. For each character
(characters.json):

1. Body: MPFB (the commit build.sh pins) makes this character's body from its macro details and detail targets, and
   its game_engine rig. Same hm08 mesh, so its vertices go into Melos's skin by index (the body and the joint cubes,
   kept in MPFB's order); every shape key keeps Melos's offsets from the rest shape. Scaled to the character's height.
2. Face parts: the brows and lashes follow the skin (each vertex moves as its nearest skin vertices did); the eyes,
   teeth and tongue each take one rigid move plus scale fitted to the skin round them, so the eyes stay round.
3. Rig: the bones moved to the new body's joints (Melos's bundle bone goes).
4. Hair and beard: shells over the scalp (and the jaw, the upper lip left bare so the mouth reads, style guide) in
   layers of hair cards, a strand texture drawn here (straight, combed back, curly or tied up in a bun).
5. Clothes ("Tunic", one material): pieces cut from MPFB's own helper garments (tights, skirt) and the skin, pushed
   out, cut along planes, unwrapped again; a cloth texture drawn here with a fixed seed (weave, fading, dust, stone
   dust); the skin under them goes into __under_tunic (lod_export deletes it).
6. Skin graded to the character's colour, scalp tinted to the hair, AO baked into the skin and the clothes.

Everything is seeded: two runs write the same file.
"""

import importlib
import json
import math
import os
import sys

import bpy  # first  # isort: skip

import addon_utils  # noqa: E402
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402
from mathutils.kdtree import KDTree  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[-3:]
MELOS, CID, OUT = ARGS[:3]
VARIANT = ARGS[3] if len(ARGS) > 3 else None
with open(os.path.join(HERE, "characters.json")) as f:
    CAST = json.load(f)
SPEC = dict(CAST["characters"][CID])
if VARIANT:
    SPEC.update(SPEC["variants"][VARIANT])
PAL = CAST["palette"]


FACE_PARTS_FOLLOW = ("Brows", "Lashes", "Hair")
RIGID = {"Eyes": "eye", "EyesLow": "eye", "Teeth": "mouth", "Tongue": "mouth"}
OPAQUE = {"Body", "Eyes", "EyesLow", "Teeth", "Tongue"}
ROUGH = {
    "Body": 0.55,
    "Eyes": 0.12,
    "EyesLow": 0.12,
    "Teeth": 0.3,
    "Tongue": 0.35,
    "Hair": 0.85,
    "Brows": 0.6,
    "Lashes": 0.6,
    "Tunic": 1.0,
}
SPECULAR = {"Hair": 0.25, "Tunic": 0.25}
MAT_NAME = {
    "Body": "skin",
    "Eyes": "eyes",
    "EyesLow": "eyes",
    "Teeth": "teeth",
    "Tongue": "tongue",
    "Hair": "hair",
    "Brows": "brows",
    "Lashes": "lashes",
    "Tunic": "tunic",
}
SKIN_SAT = 0.9
AO_SAMPLES = 24
SEED = sum(map(ord, CID + (VARIANT or "")))
report = {"id": SPEC["id"], "variant": VARIANT}


def hexrgb(h):
    h = PAL.get(h, h).lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def to_lin(c):
    return np.clip(c, 0, 1) ** 2.2


def to_srgb(c):
    return np.clip(c, 0, 1) ** (1 / 2.2)


def image_pixels(img):
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(h, w, 4)


def activate(ob):
    """Make ob the only selected and the active object (mode_set and the UV operators read the view layer)."""
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    ob.hide_set(False)
    ob.select_set(True)
    vl.objects.active = ob


def ctx(ob, sel=None):
    sel = sel or [ob]
    return bpy.context.temp_override(object=ob, active_object=ob, selected_objects=sel, selected_editable_objects=sel)


def coords(ob):
    a = np.empty(len(ob.data.vertices) * 3, np.float64)
    ob.data.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


def set_coords(ob, co, keys=True):
    """New rest positions; every shape key keeps its offset from the rest shape."""
    me = ob.data
    old = coords(ob)
    if keys and me.shape_keys:
        for kb in me.shape_keys.key_blocks:
            k = np.empty(len(me.vertices) * 3)
            kb.data.foreach_get("co", k)
            kb.data.foreach_set("co", (co + (k.reshape(-1, 3) - old)).ravel())
    me.vertices.foreach_set("co", np.asarray(co, np.float64).ravel())
    me.update()


# ---------------------------------------------------------------- 1. body


def mpfb(name):
    return importlib.import_module("bl_ext.user_default.mpfb.services." + name)


def in_group_mask(ob, name, cut=0.5):
    gi = ob.vertex_groups[name].index
    m = np.zeros(len(ob.data.vertices), bool)
    for v in ob.data.vertices:
        m[v.index] = any(g.group == gi and g.weight > cut for g in v.groups)
    return m


def make_body():
    """MPFB's human for this character: (object, rig, world coordinates of every vertex)."""
    HS = mpfb("humanservice").HumanService
    TS = mpfb("targetservice").TargetService
    details = TS.get_default_macro_info_dict()
    details.update({k: v for k, v in SPEC["macro"].items()})
    details["race"] = {"caucasian": 0.6, "african": 0.2, "asian": 0.2}
    base = HS.create_human(macro_detail_dict=details)
    for name, w in sorted(SPEC.get("details", {}).items()):
        path = TS.target_full_path(name)
        if path is None:
            raise SystemExit(f"no MPFB target {name}")
        TS.load_target(base, path, weight=w)
    for m in list(base.modifiers):
        if m.type == "MASK":
            base.modifiers.remove(m)
    activate(base)
    bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
    rig = HS.add_builtin_rig(base, "game_engine")
    mw = base.matrix_world
    co = np.array([(mw @ v.co)[:] for v in base.data.vertices])
    return base, rig, co


def melos_index(base):
    """The base mesh vertices Melos's skin kept (the body and the joint cubes), in order."""
    keep = in_group_mask(base, "body") | in_group_mask(base, "JointCubes")
    return np.flatnonzero(keep)


def similarity(src, dst):
    """Scale, rotation and offset taking src points onto dst (Umeyama), as a 4x4."""
    ms, md = src.mean(0), dst.mean(0)
    a, b = src - ms, dst - md
    u, s, vt = np.linalg.svd(b.T @ a / len(src))
    d = np.eye(3)
    d[2, 2] = np.sign(np.linalg.det(u @ vt))
    r = u @ d @ vt
    scale = np.trace(np.diag(s) @ d) / (a**2).sum(1).mean()
    m = np.eye(4)
    m[:3, :3] = scale * r
    m[:3, 3] = md - scale * r @ ms
    return m


def follow(old_body, new_body, pts, k=8):
    """Each point moved as its k nearest skin vertices moved (inverse distance weights)."""
    kd = KDTree(len(old_body))
    for i, c in enumerate(old_body):
        kd.insert(c, i)
    kd.balance()
    disp = new_body - old_body
    out = np.empty_like(pts)
    for j, p in enumerate(pts):
        near = kd.find_n(Vector(p), k)
        w = np.array([1.0 / max(d, 1e-4) ** 2 for _, _, d in near])
        out[j] = p + (w[:, None] * disp[[i for _, i, _ in near]]).sum(0) / w.sum()
    return out


def reshape():
    body = bpy.data.objects["Body"]
    old = coords(body)
    base, rig_new, co = make_body()
    idx = melos_index(base)
    if len(idx) != len(old):
        raise SystemExit(f"Melos's skin has {len(old)} vertices, the MPFB body and joint cubes {len(idx)}")
    new = co[idx]
    report["melos_offset_median_m"] = round(float(np.median(np.linalg.norm(new - old, axis=1))), 4)
    # ground and height: the soles on z = 0, the crown at the character's height (the joint cubes left out)
    skin = in_group_mask(body, "body")
    lo = new[skin, 2].min()
    hi = new[skin, 2].max()
    scale = SPEC["height"] / (hi - lo)
    ground = old[skin, 2].min()  # where Melos's soles are (MPFB's feet_on_ground counts the helpers)

    def fit(p):
        return (p - np.array([0.0, 0.0, lo])) * scale + np.array([0.0, 0.0, ground])

    new = fit(new)
    # MPFB's joint cubes come out of the container's build collapsed (zero-area faces, which Surface Deform in
    # lod_export refuses to bind to): they keep Melos's and follow the skin round them
    cubes = ~skin
    new[cubes] = follow(old[skin], new[skin], old[cubes], k=4)
    report["height_m"] = round(float(new[skin, 2].max() - ground), 3)
    report["scale"] = round(float(scale), 4)

    # face parts, before the skin moves
    for name in FACE_PARTS_FOLLOW:
        ob = bpy.data.objects[name]
        set_coords(ob, follow(old, new, coords(ob)))
    for name, region in RIGID.items():
        ob = bpy.data.objects[name]
        pts = coords(ob)
        sides = [pts[:, 0] > 0, pts[:, 0] <= 0] if region == "eye" else [np.ones(len(pts), bool)]
        out = pts.copy()
        for sel in sides:
            if not sel.any():
                continue
            c = pts[sel].mean(0)
            r = 0.035 if region == "eye" else 0.05
            near = np.flatnonzero(np.linalg.norm(old - c, axis=1) < r)
            m = similarity(old[near], new[near])
            out[sel] = pts[sel] @ m[:3, :3].T + m[:3, 3]
        set_coords(ob, out)
    set_coords(body, new)

    # rig: the new body's joints
    rig = bpy.data.objects["Rig"]
    heads = {
        b.name: (np.array((rig_new.matrix_world @ b.head_local)[:]), np.array((rig_new.matrix_world @ b.tail_local)[:]))
        for b in rig_new.data.bones
    }
    rolls = {}
    activate(rig_new)
    bpy.ops.object.mode_set(mode="EDIT")
    for eb in rig_new.data.edit_bones:
        rolls[eb.name] = eb.roll
    bpy.ops.object.mode_set(mode="OBJECT")
    inv = np.array(rig.matrix_world.inverted())
    activate(rig)
    bpy.ops.object.mode_set(mode="EDIT")
    if True:
        for eb in list(rig.data.edit_bones):
            if eb.name == "root" and "Root" in heads:
                heads["root"] = heads["Root"]
                rolls["root"] = rolls["Root"]
            if eb.name not in heads:
                rig.data.edit_bones.remove(eb)
                continue
            h, t = heads[eb.name]
            eb.head = Vector((inv @ np.append(fit(h), 1))[:3])
            eb.tail = Vector((inv @ np.append(fit(t), 1))[:3])
            eb.roll = rolls[eb.name]
    bpy.ops.object.mode_set(mode="OBJECT")
    report["bones"] = len(rig.data.bones)
    bpy.data.objects.remove(rig_new, do_unlink=True)
    for ob in bpy.data.objects:  # Melos's bundle bone is gone
        if ob.type == "MESH" and "bundle" in ob.vertex_groups:
            ob.vertex_groups.remove(ob.vertex_groups["bundle"])
    return base, fit(co)


# ---------------------------------------------------------------- landmarks


def bone_world(name, tail=False):
    rig = bpy.data.objects["Rig"]
    b = rig.data.bones[name]
    return np.array((rig.matrix_world @ (b.tail_local if tail else b.head_local))[:])


def landmarks():
    body = bpy.data.objects["Body"]
    co = coords(body)
    lips = in_group_mask(body, "lips")
    eyes = coords(bpy.data.objects["Eyes"])
    lm = {
        "neck": bone_world("neck_01"),
        "head": bone_world("head"),
        "chest": bone_world("spine_03"),
        "pelvis": bone_world("pelvis"),
        "thigh_l": bone_world("thigh_l"),
        "thigh_r": bone_world("thigh_r"),
        "ankle_l": bone_world("foot_l"),
        "ankle_r": bone_world("foot_r"),
        "shoulder_l": bone_world("upperarm_l"),
        "shoulder_r": bone_world("upperarm_r"),
        "elbow_l": bone_world("lowerarm_l"),
        "elbow_r": bone_world("lowerarm_r"),
        "hand_r": bone_world("hand_r"),
        "hand_r_tip": bone_world("hand_r", tail=True),
        "mouth": co[lips].mean(0),
        "mouth_lo": co[lips, 2].min(),
        "mouth_hi": co[lips, 2].max(),
        "eye": eyes.mean(0),
        "ground": float(co[in_group_mask(body, "body"), 2].min()),
        "crown": float(co[in_group_mask(body, "body"), 2].max()),
    }
    return lm


def dominant_bones(ob):
    rig = bpy.data.objects["Rig"]
    names = {g.index: g.name for g in ob.vertex_groups if g.name in rig.data.bones}
    out = []
    for v in ob.data.vertices:
        best, w = None, 0.0
        for g in v.groups:
            n = names.get(g.group)
            if n is not None and g.weight > w:
                best, w = n, g.weight
        out.append(best)
    return out


# ---------------------------------------------------------------- shells (hair, beard, clothes)


def mesh_bm(verts, faces):
    bm = bmesh.new()
    bv = [bm.verts.new(v) for v in verts]
    for f in faces:
        try:
            bm.faces.new([bv[i] for i in f])
        except ValueError:
            pass
    bm.normal_update()
    return bm


def vertex_normals(co, faces):
    n = np.zeros_like(co)
    for f in faces:
        p = co[list(f)]
        fn = np.cross(p[1] - p[0], p[2] - p[0])
        if len(f) == 4:
            fn += np.cross(p[2] - p[0], p[3] - p[0])
        for i in f:
            n[i] += fn
    ln = np.linalg.norm(n, axis=1)
    return n / np.maximum(ln, 1e-12)[:, None]


def shell(co, faces, pick, offset, normals=None):
    """The faces in pick (indices into faces), their vertices pushed out by offset (a number, or per vertex):
    (verts, faces, source vertex per new vertex)."""
    normals = vertex_normals(co, faces) if normals is None else normals
    used = sorted({i for fi in pick for i in faces[fi]})
    remap = {i: k for k, i in enumerate(used)}
    off = offset if np.ndim(offset) == 0 else np.asarray(offset)[used]
    verts = co[used] + normals[used] * (off if np.ndim(off) == 0 else off[:, None])
    return verts, [[remap[i] for i in faces[fi]] for fi in pick], np.array(used)


def cut(bm, planes):
    """Delete what lies on the positive side of each plane (point, normal), cutting the faces along it."""
    for p, n in planes:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=Vector(p), plane_no=Vector(n).normalized(), clear_outer=True)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")


def cut_all(bm, planes):
    """Delete what lies on the positive side of every one of the planes at once (a neckline: lower in front, rising
    over the shoulders); the faces are split along each plane first, so the edge is clean."""
    for p, n in planes:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=Vector(p), plane_no=Vector(n).normalized())
    ns = [(Vector(p), Vector(n).normalized()) for p, n in planes]
    gone = [f for f in bm.faces if min((f.calc_center_median() - p).dot(n) for p, n in ns) > 0]
    bmesh.ops.delete(bm, geom=gone, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")


def body_faces(ob):
    return [tuple(p.vertices) for p in ob.data.polygons]


def new_object(name, bm, material=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    rig = bpy.data.objects["Rig"]
    ob.parent = rig
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = rig
    if material is not None:
        me.materials.append(material)
    return ob


def copy_weights(dst, src, src_idx=None, exclude=(), k=4, pts=None):
    """dst's vertex weights from src's: one source vertex each (src_idx), or the k nearest (inverse distance)."""
    sco = coords(src)
    bones = set(bpy.data.objects["Rig"].data.bones.keys())
    sw = [
        {
            src.vertex_groups[g.group].name: g.weight
            for g in v.groups
            if src.vertex_groups[g.group].name in bones and src.vertex_groups[g.group].name not in exclude
        }
        for v in src.data.vertices
    ]
    groups = {}

    def group(n):
        if n not in groups:
            groups[n] = dst.vertex_groups.get(n) or dst.vertex_groups.new(name=n)
        return groups[n]

    dco = coords(dst) if pts is None else pts
    if src_idx is None:
        kd = KDTree(len(sco))
        for i, c in enumerate(sco):
            if sw[i]:
                kd.insert(c, i)
        kd.balance()
    for j in range(len(dst.data.vertices)):
        if src_idx is not None:
            acc = dict(sw[src_idx[j]])
        else:
            acc = {}
            near = kd.find_n(Vector(dco[j]), k)
            ws = [1.0 / max(d, 1e-4) ** 2 for _, _, d in near]
            for (_, i, _), w in zip(near, ws):
                for n, x in sw[i].items():
                    acc[n] = acc.get(n, 0.0) + x * w / sum(ws)
        top = sorted(acc.items(), key=lambda t: -t[1])[:4]
        tot = sum(x for _, x in top) or 1.0
        for n, x in top:
            group(n).add([j], x / tot, "REPLACE")


def copy_keys(dst, src, src_idx, normals_src=None, offset=None):
    """dst (a shell over src's vertices src_idx) takes src's shape keys: each vertex moves as its source does."""
    sk = src.data.shape_keys
    if not sk:
        return
    base = np.empty(len(src.data.vertices) * 3)
    sk.key_blocks[0].data.foreach_get("co", base)
    base = base.reshape(-1, 3)
    dco = coords(dst)
    dst.shape_key_add(name="Basis", from_mix=False)
    tmp = np.empty_like(base.ravel())
    for kb in sk.key_blocks[1:]:
        kb.data.foreach_get("co", tmp)
        d = tmp.reshape(-1, 3)[src_idx] - base[src_idx]
        if np.abs(d).max() < 1e-5:
            continue
        nk = dst.shape_key_add(name=kb.name, from_mix=False)
        nk.data.foreach_set("co", (dco + d).ravel())


# ---------------------------------------------------------------- textures drawn here


def value_noise(shape, cell, rng):
    h, w = shape
    gh, gw = h // cell + 2, w // cell + 2
    g = rng.random((gh, gw)).astype(np.float32)
    y = np.arange(h) / cell
    x = np.arange(w) / cell
    y0, x0 = y.astype(int), x.astype(int)
    fy, fx = (y - y0)[:, None], (x - x0)[None, :]
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    a = g[y0][:, x0]
    b = g[y0][:, x0 + 1]
    c = g[y0 + 1][:, x0]
    d = g[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def strand_texture(w, h, rng, along="v", curl=0.0, density=0.55):
    """Hair strands as an RGBA tile (float, rows top-first): thin lines along v (or u), curled by `curl`, their
    shade varied; alpha where a strand is. Colour is grey, tinted by the hair colour later."""
    img = Image.new("LA", (w, h), (0, 0))
    draw = ImageDraw.Draw(img)
    n = int(w * h / 90 * density)
    for _ in range(n):
        x, y = rng.random() * w, rng.random() * h
        length = rng.uniform(0.04, 0.12) * h
        shade = int(rng.uniform(110, 230))
        pts = []
        steps = 8
        ang = rng.uniform(-0.25, 0.25)
        for s in range(steps + 1):
            t = s / steps
            wob = curl * math.sin(t * math.pi * 2 * rng.uniform(1.5, 3.0) + rng.random() * 6) * 0.02 * h
            if along == "v":
                pts.append((x + wob + ang * t * length, y + t * length))
            else:
                pts.append((x + t * length, y + wob + ang * t * length))
        draw.line(pts, fill=(shade, 255), width=max(1, int(rng.uniform(1, 2.6))))
    a = np.asarray(img, np.float32) / 255
    out = np.zeros((h, w, 4), np.float32)
    out[..., :3] = a[..., :1]
    out[..., 3] = a[..., 1]
    return out


def set_image(img, px_top_first):
    """px rows top-first (as a PNG) into a Blender image (rows bottom-up)."""
    img.pixels.foreach_set(np.ascontiguousarray(px_top_first[::-1]).ravel())
    img.pack()


# ---------------------------------------------------------------- 4. hair and beard

HAIR_SIZE = 2048


def build_hair(lm):
    """The Hair object: Melos's afro cards pulled close to the head (curly), or shells over the scalp; and the beard.
    One image: the top half the afro texture (curly), the bottom left scalp strands, the bottom right beard strands."""
    body = bpy.data.objects["Body"]
    old_hair = bpy.data.objects["Hair"]
    mat = old_hair.data.materials[0]
    nt = mat.node_tree
    tex_node = nt.nodes["diffuseTexture"]
    afro = tex_node.image
    hs = SPEC["hair"]
    rng = np.random.default_rng(SEED)
    colour = np.asarray(hexrgb(hs["colour"]), np.float32) / 255
    atlas = np.zeros((HAIR_SIZE, HAIR_SIZE, 4), np.float32)
    half = HAIR_SIZE // 2
    # top half: afro (rows top-first)
    ap = image_pixels(afro)[::-1]
    atlas[:half] = (
        np.asarray(
            Image.fromarray((ap * 255).astype(np.uint8), "RGBA").resize((HAIR_SIZE, half), Image.LANCZOS), np.float32
        )
        / 255
    )
    curl = 1.0 if hs["style"] == "curly" else 0.15
    atlas[half:, :half] = strand_texture(half, half, rng, "v", curl, 0.9)
    atlas[half:, half:] = strand_texture(half, half, rng, "v", 0.6 if hs["style"] == "curly" else 0.3, 0.8)
    # grey-tinted by the hair's colour (linear), with some grey hairs
    lum = atlas[..., :3].mean(-1, keepdims=True)
    base_col = to_lin(colour)
    tinted = to_lin(np.clip(lum * 1.2, 0, 1)) * base_col / max(base_col.mean(), 1e-3) * base_col.mean() * 1.6
    if hs.get("grey"):
        g = (rng.random(lum.shape[:2]) < hs["grey"]).astype(np.float32)[..., None]
        g = (
            np.asarray(
                Image.fromarray((g[..., 0] * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)), np.float32
            )[..., None]
            / 255
        )
        tinted = tinted * (1 - g) + to_lin(np.array([0.72, 0.70, 0.67])) * lum * g
    atlas[..., :3] = to_srgb(tinted)
    img = bpy.data.images.new("hair_" + CID, HAIR_SIZE, HAIR_SIZE, alpha=True)
    set_image(img, atlas)

    co = coords(body)
    faces = body_faces(body)
    scalp = in_group_mask(body, "scalp")
    normals = vertex_normals(co, faces)
    pieces = []  # (bmesh, source vertex indices, uv function)

    head_c = lm["head"] + np.array([0, 0, 0.09])
    if hs["style"] == "curly":
        # Melos's afro cards, pulled towards the scalp to the character's length, UVs into the top half
        hco = coords(old_hair)
        bvh = BVHTree.FromPolygons([Vector(c) for c in co], faces)
        near = np.array([bvh.find_nearest(Vector(c))[0][:] for c in hco])
        dist = np.linalg.norm(hco - near, axis=1)
        k = np.clip(hs["length"] / max(np.percentile(dist, 90), 1e-3), 0.3, 1.0)
        set_coords(old_hair, near + (hco - near) * k)
        uvl = old_hair.data.uv_layers[0].data
        for lp in uvl:
            lp.uv = (lp.uv[0], 0.5 + 0.5 * lp.uv[1])
        hair = old_hair
    else:
        bpy.data.objects.remove(old_hair, do_unlink=True)
        hair = None

    # scalp shells: faces all in the scalp group (MPFB's), and for the bun a lump at the back
    pick = [fi for fi, f in enumerate(faces) if scalp[list(f)].all()]
    layers = [] if hs["style"] == "curly" else [0.35, 0.7, 1.0]
    span = co[[i for fi in pick for i in faces[fi]]]
    x0, x1 = span[:, 0].min(), span[:, 0].max()
    y0, y1 = span[:, 1].min(), span[:, 1].max()
    for t in layers:
        verts, fs, src = shell(co, faces, pick, 0.0015 + hs["length"] * t, normals)
        bm = mesh_bm(verts, fs)
        uv = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            for lp in f.loops:
                p = lp.vert.co
                # from above: u across, v front to back (the strands lie front to back: combed back)
                u = (p.x - x0) / (x1 - x0)
                v = (p.y - y0) / (y1 - y0)
                lp[uv].uv = (0.01 + 0.48 * u, 0.01 + 0.48 * (1 - v))
        pieces.append((bm, src))
    beard = SPEC.get("beard")
    if beard:
        mz, my = lm["mouth"][2], lm["mouth"][1]
        lips = in_group_mask(body, "lips")
        lip_ring = lips.copy()
        for _ in range(1):  # the upper lip and the corners stay bare (style guide: the mouth must read)
            grow = lip_ring.copy()
            for f in faces:
                if lip_ring[list(f)].any():
                    grow[list(f)] = True
            lip_ring = grow
        dom = dominant_bones(body)

        def in_beard(i):
            c = co[i]
            if lip_ring[i] or dom[i] not in ("head", "neck_01"):
                return False
            if c[2] > mz + 0.022 or c[2] < mz - 0.07:
                return False
            if c[1] > my + 0.06:  # behind the jaw's corner
                return False
            if c[2] > lm["mouth_hi"] + 0.003:  # above the mouth: a moustache only, the cheeks stay bare
                return abs(c[0]) < 0.028 and c[2] < lm["mouth_hi"] + 0.014
            return abs(c[0]) < 0.068 and (c[2] < mz - 0.012 or abs(c[0]) > 0.03)

        on = np.array([in_beard(i) for i in range(len(co))])
        bpick = [fi for fi, f in enumerate(faces) if on[list(f)].all()]
        bz0, bz1 = mz - 0.085, mz + 0.03
        for t in (0.25, 0.5, 0.75):
            verts, fs, src = shell(co, faces, bpick, 0.0008 + beard["length"] * t, normals)
            bm = mesh_bm(verts, fs)
            uv = bm.loops.layers.uv.new("UVMap")
            for f in bm.faces:
                for lp in f.loops:
                    p = lp.vert.co
                    u = (p.x + 0.08) / 0.16
                    v = (p.z - bz0) / (bz1 - bz0)
                    lp[uv].uv = (0.51 + 0.48 * np.clip(u, 0, 1), 0.01 + 0.48 * np.clip(v, 0, 1))
            pieces.append((bm, src))
        report["beard_faces"] = len(bpick)

    shells = []
    for bm, src in pieces:
        ob = new_object("HairShell", bm)
        copy_weights(ob, body, src_idx=src)
        copy_keys(ob, body, src)
        shells.append(ob)
    if hair is None and not shells:
        raise SystemExit("no hair")
    if hair is None:
        hair = shells.pop(0)
        hair.name = "Hair"
        hair.data.materials.append(mat)
    for ob in shells:
        ob.data.materials.append(mat)
    if shells:
        activate(hair)
        for o in shells:
            o.select_set(True)
        bpy.ops.object.join()
    hair.name = "Hair"
    tex_node.image = img
    # the strands fade out at the shells' edges: alpha down where the scalp/beard region ends (in texture space)
    report["hair_tris"] = sum(len(p.vertices) - 2 for p in hair.data.polygons)
    return hair


# ---------------------------------------------------------------- 5. clothes

TORSO = {"pelvis", "spine_01", "spine_02", "spine_03", "clavicle_l", "clavicle_r"}
LEGS = {"thigh_l", "thigh_r", "calf_l", "calf_r"}
FEET = {"foot_l", "foot_r", "ball_l", "ball_r"}
TEX = 1024
PIECE_KIND = []  # piece index -> garment spec


def base_parts(base, fco):
    """The MPFB base mesh at the character's shape: coordinates, faces, normals, dominant bone, helper masks."""
    faces = [tuple(p.vertices) for p in base.data.polygons]
    normals = vertex_normals(fco, faces)
    dom = dominant_bones(base)
    return {
        "co": fco,
        "faces": faces,
        "n": normals,
        "dom": dom,
        "tights": in_group_mask(base, "helper-tights"),
        "skirt": in_group_mask(base, "helper-skirt"),
        "body": in_group_mask(base, "body"),
    }


def faces_where(bp, mask, test):
    out = []
    for fi, f in enumerate(bp["faces"]):
        if mask[list(f)].all():
            c = bp["co"][list(f)].mean(0)
            if test(fi, f, c):
                out.append(fi)
    return out


def majority(bp, f, names):
    return sum(bp["dom"][i] in names for i in f) * 2 > len(f)


def neckline_planes(lm, drop=0.035, front=0.35):
    z0 = np.array([0, 0, lm["neck"][2] - drop])
    return [(z0, (0, -front, 1)), (z0 + [0.09, 0, 0], (-1.0, -front, 1)), (z0 - [0.09, 0, 0], (1.0, -front, 1))]


def on_arm(lm, c, sleeves):
    """Is c on an arm past where the sleeve ends (none: at the shoulder joint, short: a third down the upper arm,
    half: half way)? Faces, not a plane: a plane through the shoulder would cut the torso too."""
    t = {"none": 0.12, "short": 0.38, "half": 0.55}[sleeves]
    for s in "lr":
        a, b = lm["shoulder_" + s], lm["elbow_" + s]
        d = b - a
        L = np.linalg.norm(d)
        u = float(np.dot(c - a, d)) / (L * L)
        if u > t and np.linalg.norm(c - (a + d * u)) < 0.095:
            return True
    return False


def diagonal_plane(p1, p2, bare_point):
    """A plane through p1 and p2 (in the x-z plane, running front to back) facing bare_point: what lies on that
    side goes (the bare shoulder of an exomis, the free shoulder under a himation)."""
    d = np.asarray(p2, float) - np.asarray(p1, float)
    n = np.array([d[2], 0.0, -d[0]])
    if np.dot(n, np.asarray(bare_point) - p1) < 0:
        n = -n
    return (np.asarray(p1, float), n)


def piece(bm_all, layer, verts, fs, kind_index):
    bm = mesh_bm(verts, fs)
    return bm


def garment_pieces(bp, lm):
    """bmesh pieces with the garment spec index they belong to."""
    out = []
    co = bp["co"]
    hip_z = lm["pelvis"][2]
    gz = lm["ground"]
    for gi, g in enumerate(SPEC["garments"]):
        k = g["kind"]
        if k == "chiton":
            hem = gz + g["hem"]
            sl = g.get("sleeves", "short")
            upper = faces_where(
                bp,
                bp["tights"],
                lambda fi, f, c: (
                    majority(bp, f, TORSO | {"upperarm_l", "upperarm_r"})
                    and c[2] > hip_z - 0.12
                    and not on_arm(lm, c, sl)
                ),
            )
            verts, fs, _ = shell(co, bp["faces"], upper, 0.011, bp["n"])
            bm = mesh_bm(verts, fs)
            cut_all(bm, neckline_planes(lm))
            planes = []
            if g.get("bare"):
                s = 1 if g["bare"] == "l" else -1  # the character's left is +x
                chest, neck = lm["chest"][2], lm["neck"][2]
                planes.append(
                    diagonal_plane(
                        [s * 0.15, 0, chest + 0.10], [-s * 0.05, 0, neck - 0.04], lm["shoulder_" + g["bare"]]
                    )
                )
            cut(bm, planes)
            out.append((bm, gi))
            skirt = faces_where(bp, bp["skirt"], lambda fi, f, c: c[2] > hem - 0.01)
            verts, fs, _ = shell(co, bp["faces"], skirt, 0.014, bp["n"])
            bm = mesh_bm(verts, fs)
            cut(bm, [(np.array([0, 0, hem]), (0, 0, -1))])
            out.append((bm, gi))
        elif k == "himation":
            hem = gz + g["hem"]
            off = 0.034 if g.get("heavy") else 0.026
            s = 1 if g.get("over", "l") == "l" else -1
            up = faces_where(
                bp,
                bp["tights"],
                lambda fi, f, c: (
                    majority(bp, f, TORSO | {"upperarm_l", "upperarm_r"})
                    and c[2] > hip_z - 0.12
                    and not on_arm(lm, c, "half")
                ),
            )
            verts, fs, _ = shell(co, bp["faces"], up, off, bp["n"])
            bm = mesh_bm(verts, fs)
            cut_all(bm, neckline_planes(lm, 0.02))
            planes = []
            # the other shoulder and the armpit under it stay out (draped over one shoulder, under the other arm)
            free = "r" if s == 1 else "l"
            planes.append(
                diagonal_plane(
                    [-s * 0.16, 0, lm["chest"][2] - 0.05], [s * 0.06, 0, lm["neck"][2] - 0.02], lm["shoulder_" + free]
                )
            )
            cut(bm, planes)
            out.append((bm, gi))
            sk = faces_where(bp, bp["skirt"], lambda fi, f, c: c[2] > hem - 0.01)
            verts, fs, _ = shell(co, bp["faces"], sk, off + 0.006, bp["n"])
            bm = mesh_bm(verts, fs)
            # the edge falls diagonally: lower on the draped side
            cut(bm, [(np.array([0, 0, hem]), (0, 0, -1)), (np.array([0, 0, hip_z + 0.02]), (0, 0, 1))])
            out.append((bm, gi))
        elif k == "cloak":
            top = lm["neck"][2]
            sel = faces_where(
                bp,
                bp["tights"],
                lambda fi, f, c: (
                    majority(bp, f, TORSO | {"upperarm_l", "upperarm_r"})
                    and c[2] > top - g["to"] - 0.05
                    and not on_arm(lm, c, "short")
                ),
            )
            verts, fs, _ = shell(co, bp["faces"], sel, 0.035 if g.get("fleece") else 0.026, bp["n"])
            bm = mesh_bm(verts, fs)
            cut_all(bm, neckline_planes(lm, 0.0, 0.2))
            planes = [(np.array([0, 0, top - g["to"]]), (0, 0, -1))]
            cut(bm, planes)
            out.append((bm, gi))
        elif k == "apron":
            hem = gz + g["hem"]
            sel = faces_where(bp, bp["skirt"], lambda fi, f, c: c[2] > hem - 0.01 and c[1] < lm["pelvis"][1] - 0.02)
            verts, fs, _ = shell(co, bp["faces"], sel, 0.03, bp["n"])
            bm = mesh_bm(verts, fs)
            cut(
                bm,
                [
                    (np.array([0, 0, hem]), (0, 0, -1)),
                    (np.array([0.17, 0, 0]), (1, 0, 0)),
                    (np.array([-0.17, 0, 0]), (-1, 0, 0)),
                    (np.array([0, 0, hip_z + 0.06]), (0, 0, 1)),
                ],
            )
            out.append((bm, gi))
        elif k == "veil":
            # over the head and down the back to the shoulders; the face stays open
            eye = lm["eye"]
            sel = faces_where(
                bp,
                bp["body"],
                lambda fi, f, c: (
                    majority(bp, f, {"head", "neck_01", "spine_03", "clavicle_l", "clavicle_r"})
                    and c[2] > lm["chest"][2] + 0.03
                ),
            )
            verts, fs, _ = shell(co, bp["faces"], sel, 0.03, bp["n"])
            bm = mesh_bm(verts, fs)
            cut(
                bm,
                [
                    (eye + [0, 0.035, 0], (0, -1, 0.35)),  # in front of the ears and over the brow line
                    (np.array([0, 0, lm["chest"][2] + 0.05]), (0, 0, -1)),
                ],
            )
            out.append((bm, gi))
        elif k == "shoes":
            style = g["style"]
            if style == "none":
                continue
            top = gz + (0.11 if style == "closed" else 0.02)
            sel = faces_where(
                bp, bp["body"], lambda fi, f, c: majority(bp, f, FEET | {"calf_l", "calf_r"}) and c[2] < top
            )
            verts, fs, _ = shell(co, bp["faces"], sel, 0.004 if style == "closed" else 0.003, bp["n"])
            bm = mesh_bm(verts, fs)
            out.append((bm, gi))
            if style == "sandals":  # two straps: over the instep and round the ankle
                for zz, h in ((gz + 0.045, 0.012), (lm["ankle_l"][2] - 0.01, 0.012)):
                    sel = faces_where(
                        bp,
                        bp["body"],
                        lambda fi, f, c, zz=zz, h=h: (
                            majority(bp, f, FEET | {"calf_l", "calf_r"}) and abs(c[2] - zz) < h
                        ),
                    )
                    verts, fs, _ = shell(co, bp["faces"], sel, 0.0035, bp["n"])
                    bm = mesh_bm(verts, fs)
                    cut(bm, [(np.array([0, 0, zz + h / 2]), (0, 0, 1)), (np.array([0, 0, zz - h / 2]), (0, 0, -1))])
                    out.append((bm, gi))
        elif k == "band":
            z0 = lm["eye"][2] + 0.055
            h = 0.016 if g["style"] == "diadem" else 0.03
            hair = SPEC["hair"].get("length", 0.01)
            sel = faces_where(
                bp,
                bp["body"],
                lambda fi, f, c: (
                    majority(bp, f, {"head"})
                    and abs(c[2] - z0) < h
                    and c[1] > lm["eye"][1] - 0.02
                    or (majority(bp, f, {"head"}) and abs(c[2] - (z0 + 0.03)) < h and c[1] > lm["eye"][1] + 0.04)
                ),
            )
            # a ring tilted up at the back
            normal = np.array([0, 0.45, 1.0])
            verts, fs, _ = shell(co, bp["faces"], sel, hair + 0.006, bp["n"])
            bm = mesh_bm(verts, fs)
            p0 = np.array([0, lm["eye"][1], z0])
            cut(bm, [(p0 + [0, 0, h / 2], normal), (p0 - [0, 0, h / 2], -normal)])
            if g["style"] == "wreath":  # leaves: the band lumpy
                rng = np.random.default_rng(SEED + 3)
                for v in bm.verts:
                    v.co += v.normal * float(rng.uniform(0, 0.008))
            out.append((bm, gi))
        elif k == "staff":
            out.append((staff_bm(lm, g), gi))
    return out


def staff_bm(lm, g):
    """A shepherd's staff in the right hand, upright when the arm hangs down (it rests in MPFB's A pose)."""
    hand = (lm["hand_r"] + lm["hand_r_tip"]) / 2
    arm = Vector(lm["hand_r"] - lm["shoulder_r"]).normalized()
    down = Vector((0, 0, -1))
    q = arm.rotation_difference(down)  # the arm's swing down: the staff leans so that it is upright in the idle pose
    up = q.inverted() @ Vector((0, 0, 1))
    bm = bmesh.new()
    r, n = 0.016, 8
    length = g.get("length", 1.5)
    rings = []
    for t in (-0.9, -0.3, 0.3, 0.75, 1.0):
        centre = Vector(hand) + up * (t * length * 0.55)
        ax1 = up.orthogonal().normalized()
        ax2 = up.cross(ax1)
        ring = [
            bm.verts.new(centre + (ax1 * math.cos(a) + ax2 * math.sin(a)) * r)
            for a in np.linspace(0, 2 * math.pi, n, endpoint=False)
        ]
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            bm.faces.new([a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]])
    for ring in (rings[0], rings[-1]):
        bm.faces.new(ring)
    bm.normal_update()
    return bm


def build_clothes(base, fco, lm):
    bp = base_parts(base, fco)
    old = bpy.data.objects.get("Tunic")
    mat = old.data.materials[0] if old else bpy.data.materials.new("tunic")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    parts = garment_pieces(bp, lm)
    obs = []
    for bm, gi in parts:
        if not bm.faces:
            bm.free()
            continue
        pl = bm.faces.layers.int.new("piece")
        for f in bm.faces:
            f[pl] = gi
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        ob = new_object("TunicPart", bm)
        obs.append(ob)
    tunic = obs[0]
    if len(obs) > 1:
        activate(tunic)
        for o in obs:
            o.select_set(True)
        bpy.ops.object.join()
    tunic.name = "Tunic"
    tunic.data.materials.clear()
    body = bpy.data.objects["Body"]
    # weights: from the skin round each vertex (not the head's, except for what sits on the head); the staff the hand's
    piece_of = np.zeros(len(tunic.data.vertices), np.int32)
    pa = tunic.data.attributes["piece"]
    for p in tunic.data.polygons:
        for i in p.vertices:
            piece_of[i] = pa.data[p.index].value
    copy_weights(tunic, body, k=6, exclude=("bundle",))
    staff = [i for i in range(len(piece_of)) if SPEC["garments"][piece_of[i]]["kind"] == "staff"]
    if staff:
        for g in list(tunic.vertex_groups):
            g.remove(staff)
        (tunic.vertex_groups.get("hand_r") or tunic.vertex_groups.new(name="hand_r")).add(staff, 1.0, "REPLACE")
    # skirts: below the hips the weights spread over both legs and the pelvis, so the robe doesn't split
    skirt_like = {"chiton", "himation", "apron"}
    hip_z = lm["pelvis"][2]
    groups = {g.name: g for g in tunic.vertex_groups}
    for g in ("pelvis", "thigh_l", "thigh_r", "calf_l", "calf_r"):
        if g not in groups:
            groups[g] = tunic.vertex_groups.new(name=g)
    for v in tunic.data.vertices:
        if SPEC["garments"][piece_of[v.index]]["kind"] not in skirt_like or v.co.z > hip_z - 0.05:
            continue
        t = float(np.clip((hip_z - 0.05 - v.co.z) / 0.35, 0, 1))
        w = {tunic.vertex_groups[g.group].name: g.weight for g in v.groups}
        legs = sum(w.get(n, 0) for n in LEGS)
        mix = {n: x * (1 - 0.6 * t) for n, x in w.items()}
        for n, share in (("pelvis", 0.4), ("thigh_l", 0.2), ("thigh_r", 0.2), ("calf_l", 0.1), ("calf_r", 0.1)):
            mix[n] = mix.get(n, 0) + 0.6 * t * share * max(legs, 0.5) / max(legs, 0.5)
        tot = sum(mix.values())
        for n in list(w):
            groups[n].remove([v.index])
        for n, x in sorted(mix.items(), key=lambda kv: -kv[1])[:4]:
            groups[n].add([v.index], x / tot, "REPLACE")
    tunic.data.materials.append(mat)
    # smooth shading
    for p in tunic.data.polygons:
        p.use_smooth = True
    report["tunic_tris"] = len(tunic.data.polygons)
    return tunic, piece_of


def under_clothes(tunic, lm):
    """__under_tunic: the skin with cloth within 6 cm outside it (rays along the skin's normal), not the head, two
    rings in from the edge kept so no gap opens."""
    body = bpy.data.objects["Body"]
    co = coords(body)
    faces = body_faces(body)
    n = vertex_normals(co, faces)
    tco = coords(tunic)
    tf = [tuple(p.vertices) for p in tunic.data.polygons]
    keep_kinds = {"staff"}
    pa = tunic.data.attributes["piece"]
    tf = [
        f for p, f in zip(tunic.data.polygons, tf) if SPEC["garments"][pa.data[p.index].value]["kind"] not in keep_kinds
    ]
    bvh = BVHTree.FromPolygons([Vector(c) for c in tco], tf)
    dom = dominant_bones(body)
    skin = in_group_mask(body, "body")  # not the joint cubes: cut in half they leave faces Surface Deform refuses
    under = np.zeros(len(co), bool)
    for i, (c, nn) in enumerate(zip(co, n)):
        if dom[i] in ("head", "neck_01") or dom[i] is None or not skin[i]:
            continue
        hit = bvh.ray_cast(Vector(c), Vector(nn), 0.06)
        if hit[0] is not None:
            under[i] = True

    # opened (grown back after shrinking) so no thin strands or single vertices go: deleting those leaves faces
    # meeting at one corner, which Surface Deform in lod_export refuses to bind to; then two rings in from the edge
    def shrink(m):
        out = m.copy()
        for f in faces:
            if not m[list(f)].all():
                out[list(f)] = False
        return out

    def grow(m):
        out = m.copy()
        for f in faces:
            if m[list(f)].any():
                out[list(f)] = True
        return out & hit_any

    def grow_free(m):
        out = m.copy()
        for f in faces:
            if m[list(f)].any():
                out[list(f)] = True
        return out & skin & np.array([d not in ("head", "neck_01", None) for d in dom])

    # closed first: a band of skin left between two garments (the tunic's top and its skirt) would be a thin ring,
    # an island Surface Deform refuses as well
    for _ in range(3):
        under = grow_free(under)
    for _ in range(3):
        under = shrink(under)
    hit_any = under.copy()
    under = grow(shrink(under))
    for _ in range(2):
        under = shrink(under)
    g = body.vertex_groups.get("__under_tunic") or body.vertex_groups.new(name="__under_tunic")
    g.remove(list(range(len(co))))
    g.add([int(i) for i in np.flatnonzero(under)], 1.0, "REPLACE")
    report["under_tunic"] = int(under.sum())


def tunic_texture(tunic, piece_of, lm):
    """Unwrap and draw the cloth: each garment's colour (W0, L0 ... as linear means), a weave, fading on top,
    dust near the ground, stone dust (the masons), fleece lumps."""
    activate(tunic)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.006)
    bpy.ops.object.mode_set(mode="OBJECT")
    me = tunic.data
    uvl = me.uv_layers[0].data
    pa = me.attributes["piece"]
    rng = np.random.default_rng(SEED + 7)
    w = h = TEX
    px = np.zeros((h, w, 3), np.float32)
    canvas = Image.new("I", (w, h), -1)
    draw = ImageDraw.Draw(canvas)
    zs = coords(tunic)[:, 2]
    up = np.zeros(len(me.polygons))
    zmean = np.zeros(len(me.polygons))
    for p in me.polygons:
        draw.polygon([(uvl[i].uv[0] * w, (1 - uvl[i].uv[1]) * h) for i in p.loop_indices], fill=p.index)
        up[p.index] = p.normal.z
        zmean[p.index] = zs[list(p.vertices)].mean()
    fid = np.asarray(canvas, np.int32)
    # grow the face ids a few texels into the gutters (mipmaps)
    for _ in range(4):
        m = fid < 0
        if not m.any():
            break
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            sh = np.roll(np.roll(fid, dy, 0), dx, 1)
            fid = np.where(m & (sh >= 0), sh, fid)
            m = fid < 0
    valid = fid >= 0
    f = np.where(valid, fid, 0)
    gidx = np.array([pa.data[i].value for i in range(len(me.polygons))])[f]
    weave = 0.92 + 0.08 * value_noise((h, w), 2, rng) + 0.06 * (value_noise((h, w), 24, rng) - 0.5)
    for gi, g in enumerate(SPEC["garments"]):
        sel = (gidx == gi) & valid
        c = to_lin(np.asarray(hexrgb(g["colour"]), np.float32) / 255)
        if g.get("grey"):
            c = c * (1 - g["grey"]) + c.mean() * g["grey"]
        kind = g["kind"]
        if kind == "band" and g["style"] == "diadem":
            tex = 1.0 + 0.25 * (value_noise((h, w), 3, rng) - 0.5)
        elif kind in ("shoes", "staff"):
            tex = 0.85 + 0.3 * value_noise((h, w), 6, rng)
        elif g.get("fleece"):
            tex = 0.7 + 0.5 * value_noise((h, w), 5, rng) ** 1.5
        elif kind == "band":
            tex = 0.6 + 0.8 * value_noise((h, w), 4, rng)
        else:
            tex = weave
        px[sel] = c * tex[sel][:, None]
    # fading where the cloth faces up (sun), dust towards the ground, stone dust in specks
    upv, zv = up[f], zmean[f]
    cloth = np.isin(
        gidx,
        [i for i, g in enumerate(SPEC["garments"]) if g["kind"] in ("chiton", "himation", "cloak", "veil", "apron")],
    )
    fade = np.clip((upv - 0.3) / 0.6, 0, 1) * 0.18 * cloth
    px = px * (1 - fade[..., None]) + px.mean(-1, keepdims=True) * 1.25 * fade[..., None]
    dust = to_lin(np.array([152, 134, 110], np.float32) / 255)
    d = SPEC.get("dust", 0) * np.clip((0.45 - (zv - lm["ground"])) / 0.45, 0, 1) ** 1.5
    px = px * (1 - d[..., None]) + dust * d[..., None]
    if SPEC.get("stone"):
        speck = (value_noise((h, w), 1, rng) > 0.86) | (value_noise((h, w), 12, rng) > 0.8)
        s = SPEC["stone"] * (0.35 + 0.65 * speck) * cloth
        stone = to_lin(np.array([214, 210, 200], np.float32) / 255)
        px = px * (1 - s[..., None]) + stone * s[..., None]
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = to_srgb(px)
    img = bpy.data.images.new("tunic_" + CID, w, h)
    set_image(img, rgba)
    mat = me.materials[0]
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in list(nt.nodes):
        if nd.type not in ("BSDF_PRINCIPLED", "OUTPUT_MATERIAL"):
            nt.nodes.remove(nd)
    bsdf = next(nd for nd in nt.nodes if nd.type == "BSDF_PRINCIPLED")
    bsdf.name = "Principled BSDF"
    t = nt.nodes.new("ShaderNodeTexImage")
    t.name = "tunic_tex"
    t.image = img
    nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = ROUGH["Tunic"]
    bsdf.inputs["Specular IOR Level"].default_value = SPECULAR["Tunic"]
    bsdf.inputs["Metallic"].default_value = 0.0
    for lnk in list(bsdf.inputs["Alpha"].links):
        nt.links.remove(lnk)
    bsdf.inputs["Alpha"].default_value = 1.0
    return img


# ---------------------------------------------------------------- 6. materials, skin, AO


def simplify(ob):
    nt = ob.data.materials[0].node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes["diffuseTexture"]
    for n in list(nt.nodes):
        if n.type in ("MIX_RGB", "MIX", "BUMP", "NORMAL_MAP") or (n.type == "TEX_IMAGE" and n != tex):
            nt.nodes.remove(n)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if ob.name in OPAQUE:
        for link in list(bsdf.inputs["Alpha"].links):
            nt.links.remove(link)
        bsdf.inputs["Alpha"].default_value = 1.0
    else:
        nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    bsdf.inputs["Roughness"].default_value = ROUGH[ob.name]
    if ob.name in SPECULAR:
        bsdf.inputs["Specular IOR Level"].default_value = SPECULAR[ob.name]
    return tex.image


def drop_cornea(ob, img):
    px = image_pixels(img)
    h, w = px.shape[:2]
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    uvl = bm.loops.layers.uv.active
    kill = []
    for f in bm.faces:
        u, v = np.mean([lp[uvl].uv[:] for lp in f.loops], axis=0)
        if px[min(h - 1, int(v * h)), min(w - 1, int(u * w)), 3] < 0.5:
            kill.append(f)
    bmesh.ops.delete(bm, geom=kill, context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return len(kill)


def face_mask(ob, img, value, soft):
    w, h = img.size
    uvl = ob.data.uv_layers[0].data
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    for p in ob.data.polygons:
        x = value(p)
        if x:
            draw.polygon([(uvl[i].uv[0] * w, uvl[i].uv[1] * h) for i in p.loop_indices], fill=int(255 * min(1.0, x)))
    if soft:
        mask = mask.filter(ImageFilter.GaussianBlur(soft))
    return np.asarray(mask, np.float32) / 255


def grade(img, sel, target, sat=1.0):
    px = image_pixels(img)
    rgb = to_lin(px[..., :3])
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    rgb = lum[..., None] + (rgb - lum[..., None]) * sat
    gain = to_lin(np.asarray(target, np.float32) / 255) / rgb[sel].mean(0)
    px[..., :3] = to_srgb(rgb * gain)
    img.pixels.foreach_set(px.ravel())
    img.pack()
    return [round(float(g), 2) for g in gain]


def mix_towards(
    img,
    m,
    colour,
):
    px = image_pixels(img)
    c = np.asarray(colour, np.float32)
    px[..., :3] = px[..., :3] * (1 - m[..., None]) + c * m[..., None]
    img.pixels.foreach_set(px.ravel())
    img.pack()


def bake_ao(ob, size, distance):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = AO_SAMPLES
    sc.cycles.seed = 0
    sc.render.bake.margin = 8
    if sc.world is None:
        sc.world = bpy.data.worlds.new("bake")
    sc.world.light_settings.distance = distance
    target = bpy.data.images.new("ao_" + ob.name, size, size, float_buffer=True)
    nt = ob.data.materials[0].node_tree
    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = target
    nt.nodes.active = node
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    ob.select_set(True)
    vl.objects.active = ob
    bpy.ops.object.bake(type="AO")
    ao = image_pixels(target)[..., 0].copy()
    nt.nodes.remove(node)
    bpy.data.images.remove(target)
    return ao


def darken(img, ao, strength):
    px = image_pixels(img)
    if ao.shape != px.shape[:2]:
        ao = np.asarray(Image.fromarray(ao.astype(np.float32), "F").resize(img.size[:], Image.BILINEAR), np.float32)
    f = 1 - strength * (1 - np.clip(ao, 0, 1))
    px[..., :3] = to_srgb(to_lin(px[..., :3]) * f[..., None])
    img.pixels.foreach_set(px.ravel())
    img.pack()


def materials(lm):
    imgs = {}
    for name in ("Body", "Eyes", "EyesLow", "Teeth", "Tongue", "Brows", "Lashes"):
        imgs[name] = simplify(bpy.data.objects[name])
        if name == "Eyes":
            report["cornea_faces_removed"] = drop_cornea(bpy.data.objects[name], imgs[name])
    body = bpy.data.objects["Body"]
    skin = imgs["Body"]
    # Melos's skin texture is shared by the file; each character gets its own copy
    skin = skin.copy()
    skin.name = "skin_" + CID
    body.data.materials[0].node_tree.nodes["diffuseTexture"].image = skin
    report["skin_gain"] = grade(skin, face_mask(body, skin, lambda p: 1.0, 0) > 0.5, hexrgb(SPEC["skin"]), SKIN_SAT)
    brows = imgs["Brows"].copy()
    bpy.data.objects["Brows"].data.materials[0].node_tree.nodes["diffuseTexture"].image = brows
    grade(brows, image_pixels(brows)[..., 3] > 0.5, hexrgb(SPEC.get("brows", SPEC["hair"]["colour"])))
    # scalp and beard stubble towards the hair's colour
    hair_c = np.asarray(hexrgb(SPEC["hair"]["colour"]), np.float32) / 255 * 0.85
    scalp = in_group_mask(body, "scalp")
    mix_towards(skin, face_mask(body, skin, lambda p: 0.92 if scalp[list(p.vertices)].all() else None, 10), hair_c)
    if SPEC.get("beard"):
        co = coords(body)
        mz = lm["mouth"][2]
        lips = in_group_mask(body, "lips")

        def stubble(p):
            c = co[list(p.vertices)].mean(0)
            if lips[list(p.vertices)].any() or c[1] > lm["mouth"][1] + 0.075 or abs(c[0]) > 0.075:
                return None
            return 0.45 if mz - 0.085 < c[2] < mz + 0.03 else None

        mix_towards(skin, face_mask(body, skin, stubble, 6), hair_c * 0.8)
    # dust on the shins and feet
    if SPEC.get("dust"):
        z = coords(body)[:, 2]
        legs = face_mask(
            body,
            skin,
            lambda p: SPEC["dust"] * np.clip((lm["ground"] + 0.45 - z[list(p.vertices)].mean()) / 0.42, 0, 1),
            6,
        )
        mix_towards(skin, legs, np.array([152, 134, 110], np.float32) / 255)
    return skin


def ambient_occlusion(skin, tunic_img):
    bpy.data.objects["EyesLow"].hide_render = True
    body = bpy.data.objects["Body"]
    ao = np.clip(bake_ao(body, 1024, 0.06), 0, 1)
    darken(skin, ao, 0.5)
    tunic = bpy.data.objects["Tunic"]
    darken(tunic_img, np.clip(bake_ao(tunic, 1024, 0.08), 0, 1), 0.75)
    bpy.data.objects["EyesLow"].hide_render = False


# ---------------------------------------------------------------- main


def main():
    bpy.ops.wm.open_mainfile(filepath=MELOS)
    addon_utils.enable("bl_ext.user_default.mpfb", default_set=True)
    for ob in bpy.data.objects:
        if ob.mode == "EDIT":  # EyesLow was saved in edit mode on the Mac: its UVs read empty until it leaves
            with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob], edit_object=ob):
                bpy.ops.object.mode_set(mode="OBJECT")
    base, fco = reshape()
    lm = landmarks()
    report["landmarks"] = {
        k: (round(float(v), 3) if np.ndim(v) == 0 else [round(float(x), 3) for x in v]) for k, v in lm.items()
    }
    skin = materials(lm)
    hair = build_hair(lm)
    simplify(hair)
    tunic, piece_of = build_clothes(base, fco, lm)
    bpy.data.objects.remove(base, do_unlink=True)
    under_clothes(tunic, lm)
    tunic_img = tunic_texture(tunic, piece_of, lm)
    ambient_occlusion(skin, tunic_img)
    for name, mat_name in MAT_NAME.items():
        bpy.data.objects[name].data.materials[0].name = mat_name
    for img in bpy.data.images:
        if img.packed_file:
            img.filepath_raw = os.path.basename(img.filepath_raw) or img.name
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    report["tris"] = {
        o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in bpy.data.objects if o.type == "MESH"
    }
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(OUT), compress=True)
    print("CAST_REPORT " + json.dumps(report))


main()
