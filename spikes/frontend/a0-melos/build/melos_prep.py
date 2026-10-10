"""Get the MPFB build of Melos from the Mac ready for lod_export.py (A-0 step 3).

$BPY melos_prep.py <melos.blend> <tex_dir from melos_tex.py> <out.blend>

- Materials: MPFB puts a Mix node (factor 1) between the diffuse texture and Base Color and links the texture's
  alpha into Alpha on every part. The glTF exporter follows neither: it would drop the texture and write every
  material as BLEND. So the texture goes straight into Base Color, bump nodes go, and skin, eyes, teeth and tongue
  become opaque; hair, brows and lashes keep their alpha (merge_parts turns it into a mask).
- Eyes: the cornea shell sits on the transparent part of the eye texture; opaque, it would hide the iris. Removed.
- An object saved in edit mode (EyesLow, on the Mac) is taken back to object mode: until then its UVs read empty.
- Skin: the scalp (MakeHuman's `scalp` vertex group) painted towards the hair colour with a soft edge, so the skin
  between the hair cards and along the hairline reads as hair instead of a bright ragged line.
- Roughness per part (MPFB sets 0.7 everywhere); materials renamed as on the stand-in (skin, eyes, hair, ...):
  compress.mjs and the test page find the skin and the alpha-tested parts by material name.
- Tunic: tunic_base.png and tunic_nrm.png from melos_tex.py, packed into the file; triangulated (the sole hulls are
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


def image_pixels(img):
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(h, w, 4)


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
for name in ("Body", "Eyes", "EyesLow", "Teeth", "Tongue", "Hair", "Brows", "Lashes"):
    img = simplify(OBJ[name])
    if name == "Eyes":
        report["cornea_faces_removed"] = drop_cornea(OBJ[name], img)
report["scalp_faces"] = scalp_tint(
    OBJ["Body"], bpy.data.images["melos_skin_diffuse"], bpy.data.images["short02_diffuse.png"]
)
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
