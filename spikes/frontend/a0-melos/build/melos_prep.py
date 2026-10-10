"""Get the MPFB build of Melos from the Mac ready for lod_export.py (A-0 step 3).

$BPY melos_prep.py <melos.blend> <tex_dir from melos_tex.py> <out.blend>

- Materials: MPFB puts a Mix node (factor 1) between the diffuse texture and Base Color and links the texture's
  alpha into Alpha on every part. The glTF exporter follows neither: it would drop the texture and write every
  material as BLEND. So the texture goes straight into Base Color, bump nodes go, and skin, eyes, teeth and tongue
  become opaque; hair, brows and lashes keep their alpha (merge_parts turns it into a mask).
- Eyes: the cornea shell sits on the transparent part of the eye texture; opaque, it would hide the iris. Removed.
- An object saved in edit mode (EyesLow, on the Mac) is taken back to object mode: until then its UVs read empty.
- Colours from the style guide (docs/ux/style-guide/characters/melos.md): skin graded so its mean is the sunburnt
  #8A5A3C with a little less saturation; hair and brows graded to the same dark brown, near black.
- Skin: the scalp (MakeHuman's `scalp` vertex group) painted towards the hair colour with a soft edge, so the skin
  between the hair cards and along the hairline reads as hair instead of a bright ragged line.
- Dust from a day on the road, by height on the body: feet and shins below the knee, the tunic's hem, the sandals.
  The tunic's shoulders are faded by the sun where the cloth faces up.
- Skin normal map (new in v2; compress.mjs keeps it at 2048 on the high tier and 1024 on std): the larger relief in
  the colour map's own detail (a band-pass of its luminance). No pores (art-direction 5.1).
- Ambient occlusion baked with Cycles (rest pose, the whole figure as occluder) and multiplied into the skin and
  tunic colour maps: contact shadow under the rope, the bands, the bundle and the tunic's edges, and in the folds.
- Roughness per part (MPFB sets 0.7 everywhere); materials renamed as on the stand-in (skin, eyes, hair, ...):
  compress.mjs and the test page find the skin and the alpha-tested parts by material name.
- Tunic: tunic_base.png and tunic_nrm.png from melos_tex.py (UV regions of melos_clothes_v2), packed into the file;
  triangulated (the sole hulls are
  n-gons, and the exporter cannot compute tangents for the normal map on those).
- Image paths cut down to the file name (the Mac build recorded absolute paths with the user name; the pixels are
  packed), then unused data purged.
"""

import os
import sys

import bpy
import bmesh  # noqa: I001  (only importable after bpy)
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from melos_clothes_v2 import HEM_Z, KNEE_Z, NEW_UV

src, tex_dir, out = sys.argv[-3:]
bpy.ops.wm.open_mainfile(filepath=src)
OBJ = bpy.data.objects
OPAQUE = {"Body", "Eyes", "EyesLow", "Teeth", "Tongue"}
ROUGH = {
    "Body": 0.55,
    "Eyes": 0.12,
    "EyesLow": 0.12,
    "Teeth": 0.3,
    "Tongue": 0.35,
    "Hair": 0.5,
    "Brows": 0.6,
    "Lashes": 0.6,
    "Tunic": 0.92,
}
MAT_NAME = {"Body": "skin", "Eyes": "eyes", "EyesLow": "eyes", "Teeth": "teeth", "Tongue": "tongue", "Hair": "hair"}
MAT_NAME |= {"Brows": "brows", "Lashes": "lashes", "Tunic": "tunic"}
SKIN = (138, 90, 60)  # #8A5A3C
SKIN_SAT = 0.85
HAIR = (40, 28, 21)  # dark brown, near black
DUST = (152, 134, 110)
SUN_FADED = (196, 160, 116)
AO = {"Body": (0.5, 0.06), "Tunic": (0.85, 0.08)}  # strength, distance (m)
AO_SAMPLES = 48


def image_pixels(img):
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(h, w, 4)


def to_lin(c):
    return np.clip(c, 0, 1) ** 2.2


def to_srgb(c):
    return np.clip(c, 0, 1) ** (1 / 2.2)


def face_mask(ob, img, value, soft):
    """Rasterize value(polygon) (0..1, or None to skip) over ob's UVs at img's size; rows bottom-up like img.pixels."""
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
    """Scale img's colours (in linear light) so the mean over sel is target; sat < 1 greys them a little first."""
    px = image_pixels(img)
    rgb = to_lin(px[..., :3])
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    rgb = lum[..., None] + (rgb - lum[..., None]) * sat
    gain = to_lin(np.asarray(target, np.float32) / 255) / rgb[sel].mean(0)
    px[..., :3] = to_srgb(rgb * gain)
    img.pixels.foreach_set(px.ravel())
    img.pack()
    return [round(float(g), 2) for g in gain]


def mix_towards(img, m, colour):
    px = image_pixels(img)
    c = np.asarray(colour, np.float32) / 255
    px[..., :3] = px[..., :3] * (1 - m[..., None]) + c * m[..., None]
    img.pixels.foreach_set(px.ravel())


def z_of(ob):
    mw = ob.matrix_world
    return np.array([(mw @ v.co).z for v in ob.data.vertices], np.float32)


def uv_centre(ob, p):
    uvl = ob.data.uv_layers[0].data
    return np.mean([uvl[i].uv[:] for i in p.loop_indices], axis=0)


def in_region(c, name):
    u0, u1, v0, v1 = NEW_UV[name]
    return u0 <= c[0] <= u1 and v0 <= c[1] <= v1


def bake_ao(ob, size, distance):
    """Cycles AO of ob over its UVs at size x size (rows bottom-up); everything visible in the file occludes."""
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


def _box(a, r, ax):
    a = np.moveaxis(a, ax, 0)
    c = np.cumsum(np.pad(a, [(r + 1, r)] + [(0, 0)] * (a.ndim - 1), mode="edge"), axis=0)
    return np.moveaxis((c[2 * r + 1 :] - c[: -2 * r - 1]) / (2 * r + 1), 0, ax)


def _blur(a, sigma):
    """Gaussian blur in float (three box passes); 8-bit blurs would step the relief into fine grain."""
    r = max(1, round((np.sqrt(4 * sigma * sigma + 1) - 1) / 2))
    a = np.asarray(a, np.float64)
    for _ in range(3):
        a = _box(_box(a, r, 0), r, 1)
    return a


def skin_normal(skin, path, cover, strength=0.5):
    """Write a tangent-space normal map (OpenGL +Y, as glTF) for the skin; returns the mean lean in degrees.
    `cover`: texels inside the UV islands (top row first). Outside them the luminance is filled from the inside
    before the high-pass, and the relief is flat, so island borders don't turn into ridges."""
    px = image_pixels(skin)[::-1]  # top row first, as in the PNG
    lum = to_lin(px[..., :3]) @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    lum = lum * 255 / max(float(lum.max()), 1e-6)
    m = cover.astype(float)
    fill = _blur(lum * m, 8) / np.maximum(_blur(m, 8), 1e-3)
    lum = np.where(cover, lum, fill)
    inner = np.asarray(Image.fromarray((m * 255).astype(np.uint8), "L").filter(ImageFilter.MinFilter(5)), float) / 255
    # a band, not a high-pass: no pores or fine grain (art-direction 5.1; on a 2 cm face they turn into glitter
    # in the noon highlight), only the larger relief the colour map carries: creases, knuckles, round the eyes
    h = 10.0 * (_blur(lum, 1.5) - _blur(lum, 12)) / 255 * inner
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    nrm = np.stack([-gx * strength, gy * strength, np.ones_like(h)], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    Image.fromarray(((nrm * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8), "RGB").save(path)
    return round(float(np.degrees(np.arccos(nrm[..., 2].mean()))), 1)


def attach_normal(ob, path):
    nt = ob.data.materials[0].node_tree
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = "Non-Color"
    img.pack()
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(t.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], nt.nodes["Principled BSDF"].inputs["Normal"])


def darken(img, ao, strength):
    px = image_pixels(img)
    if ao.shape != px.shape[:2]:
        ao = np.asarray(Image.fromarray(ao.astype(np.float32), "F").resize(img.size[:], Image.BILINEAR), np.float32)
    f = 1 - strength * (1 - np.clip(ao, 0, 1))
    px[..., :3] = to_srgb(to_lin(px[..., :3]) * f[..., None])
    img.pixels.foreach_set(px.ravel())


def simplify(ob):
    nt = ob.data.materials[0].node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes["diffuseTexture"]
    for n in list(nt.nodes):
        if n.type in ("MIX_RGB", "BUMP") or (n.type == "TEX_IMAGE" and n != tex):
            nt.nodes.remove(n)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if ob.name in OPAQUE:
        for link in list(bsdf.inputs["Alpha"].links):
            nt.links.remove(link)
        bsdf.inputs["Alpha"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = ROUGH[ob.name]
    return tex.image


def drop_cornea(ob, img):
    """Delete the faces whose UV centre falls on the transparent part of the eye texture."""
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


def scalp_tint(ob, skin, hair, amount=0.85, soft=10):
    """Paint the skin texture under the scalp group towards the hair's mean opaque colour."""
    gi = ob.vertex_groups["scalp"].index
    on = np.zeros(len(ob.data.vertices), bool)
    for v in ob.data.vertices:
        on[v.index] = any(g.group == gi and g.weight > 0.5 for g in v.groups)
    w, h = skin.size
    uvl = ob.data.uv_layers[0].data
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    faces = 0
    for p in ob.data.polygons:
        if on[list(p.vertices)].all():
            draw.polygon([(uvl[i].uv[0] * w, uvl[i].uv[1] * h) for i in p.loop_indices], fill=255)
            faces += 1
    m = np.asarray(mask.filter(ImageFilter.GaussianBlur(soft)), np.float32)[..., None] / 255 * amount
    hp = image_pixels(hair).reshape(-1, 4)
    colour = hp[hp[:, 3] > 0.9, :3].mean(0)
    px = image_pixels(skin)  # rows bottom-up, like the UV v axis drawn above
    px[..., :3] = px[..., :3] * (1 - m) + colour * m
    skin.pixels.foreach_set(px.ravel())
    skin.pack()
    return faces


def tunic_textures(ob):
    nt = ob.data.materials[0].node_tree
    bsdf = nt.nodes["Principled BSDF"]
    base = bpy.data.images.load(os.path.join(tex_dir, "tunic_base.png"))
    nrm = bpy.data.images.load(os.path.join(tex_dir, "tunic_nrm.png"))
    nrm.colorspace_settings.name = "Non-Color"
    z = z_of(ob)
    mw3 = ob.matrix_world.to_3x3()

    def dust(p):
        c = uv_centre(ob, p)
        if in_region(c, "wool"):
            return 0.4 * np.clip((HEM_Z + 0.10 - z[list(p.vertices)].min()) / 0.10, 0, 1)
        return 0.35 if in_region(c, "straps") else 0.5 if in_region(c, "soles") else None

    def sun(p):
        up = (mw3 @ p.normal).z
        if not in_region(uv_centre(ob, p), "wool") or z[list(p.vertices)].mean() < 1.25:
            return None
        return 0.3 * np.clip((up - 0.3) / 0.5, 0, 1)

    mix_towards(base, face_mask(ob, base, sun, 6), SUN_FADED)
    mix_towards(base, face_mask(ob, base, dust, 4), DUST)
    darken(base, bake_ao(ob, base.size[0], AO["Tunic"][1]), AO["Tunic"][0])
    for img in (base, nrm):
        img.pack()
    nt.nodes["tunic_tex"].image = base
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = nrm
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(t.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = ROUGH["Tunic"]
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(ob.data)
    bm.free()


report = {}
for ob in OBJ:
    if ob.mode == "EDIT":
        with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob], edit_object=ob):
            bpy.ops.object.mode_set(mode="OBJECT")
        report.setdefault("left_edit_mode", []).append(ob.name)
img = {}
for name in ("Body", "Eyes", "EyesLow", "Teeth", "Tongue", "Hair", "Brows", "Lashes"):
    img[name] = simplify(OBJ[name])
    if name == "Eyes":
        report["cornea_faces_removed"] = drop_cornea(OBJ[name], img[name])
body, skin = OBJ["Body"], img["Body"]
report["skin_gain"] = grade(skin, face_mask(body, skin, lambda p: 1.0, 0) > 0.5, SKIN, SKIN_SAT)
for name in ("Hair", "Brows"):
    report[name.lower() + "_gain"] = grade(img[name], image_pixels(img[name])[..., 3] > 0.9, HAIR)
nrm_path = os.path.join(os.path.dirname(os.path.abspath(out)), "skin_nrm.png")
cover = face_mask(body, skin, lambda p: 1.0, 0)[::-1] > 0.5
report["skin_normal_lean_deg"] = skin_normal(skin, nrm_path, cover)
attach_normal(body, nrm_path)
report["scalp_faces"] = scalp_tint(body, skin, img["Hair"])
bz = z_of(body)
legs = face_mask(body, skin, lambda p: 0.5 * np.clip((KNEE_Z - bz[list(p.vertices)].mean()) / 0.42, 0, 1) ** 0.8, 6)
mix_towards(skin, legs, DUST)
OBJ["EyesLow"].hide_render = True  # the low eyes sit in the same place as the high ones
darken(skin, bake_ao(body, min(2048, skin.size[0]), AO["Body"][1]), AO["Body"][0])
OBJ["EyesLow"].hide_render = False
skin.pack()
tunic_textures(OBJ["Tunic"])
for name, mat_name in MAT_NAME.items():
    OBJ[name].data.materials[0].name = mat_name
for img in bpy.data.images:
    if img.packed_file:
        img.filepath_raw = os.path.basename(img.filepath_raw)
bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
report["tris"] = {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in OBJ if o.type == "MESH"}
report["images"] = sorted(i.name for i in bpy.data.images)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out), compress=True)
print(report)
