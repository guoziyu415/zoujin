"""Make the three character versions from one built character and export glTF.

/tmp/bpyenv/bin/python lod_export.py out/standin.blend out/glb

Versions (frontend-design 10.6.2, art-direction 9.2):
  talk_high  ~40k tris, all parts, 52 ARKit + 15 viseme morphs
  talk_std   20-30k tris: body under the clothes removed, body and teeth decimated
             with the face protected; morphs carried over with Surface Deform; clothes
             decimated except the faces in their vertex group __keep (thin tubes)
  walk       8k tris, no morphs, everything baked into one 1024 atlas, 1 material
plus anims.glb (rig + clips, shared by every character).
Works on any character with the object names used by build_standin.py; the MPFB
build on the Mac will be renamed to match.
"""

import os
import sys

import bmesh  # noqa: E402  (only importable after bpy)
import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import anims  # noqa: E402

blend, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=blend)
scene = bpy.context.scene
rig = bpy.data.objects["Rig"]
FACE_PARTS = ["Body", "Brows", "Lashes", "Teeth", "Tongue"]
TALK = ["Body", "Eyes", "Brows", "Lashes", "Teeth", "Tongue", "Hair", "Tunic"]
report = {}


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def dup(ob, name, keys=True):
    o = bpy.data.objects.new(name, ob.data.copy())
    scene.collection.objects.link(o)
    o.parent = rig
    o.matrix_parent_inverse = ob.matrix_parent_inverse.copy()
    for m in ob.modifiers:
        if m.type == "ARMATURE":
            mm = o.modifiers.new("Armature", "ARMATURE")
            mm.object = rig
    if not keys and o.data.shape_keys:
        o.shape_key_clear()
    return o


def ctx(ob):
    return bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob])


def apply_first(ob, mod):
    with ctx(ob):
        bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)
        bpy.ops.object.modifier_apply(modifier=mod.name)


def delete_group(ob, gname):
    g = ob.vertex_groups.get(gname)
    if g is None:
        return 0
    gi = g.index
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    dl = bm.verts.layers.deform.active
    kill = [v for v in bm.verts if dl and gi in v[dl] and v[dl][gi] > 0.5]
    bmesh.ops.delete(bm, geom=kill, context="VERTS")
    # edges left without a face along the cut: Surface Deform refuses a target with them ("invalid polygons")
    bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context="EDGES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_edges], context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return len(kill)


def drop_islands(ob, keep=100):
    """Remove every part of the mesh with fewer than `keep` vertices. MPFB leaves MakeHuman's joint helpers
    (small 8-vertex cubes, hidden by its Mask modifier) in the skin mesh; two stacks stood in front of the eyes.
    Only on the outputs: with the cubes gone from the Surface Deform target the bind fails ("invalid polygons")."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    seen, kill = set(), []
    for v in bm.verts:
        if v in seen:
            continue
        comp, stack = [], [v]
        seen.add(v)
        while stack:
            x = stack.pop()
            comp.append(x)
            for e in x.link_edges:
                o = e.other_vert(x)
                if o not in seen:
                    seen.add(o)
                    stack.append(o)
        if len(comp) < keep:
            kill += comp
    bmesh.ops.delete(bm, geom=kill, context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    report.setdefault("islands_removed_verts", {})[ob.name] = len(kill)
    return len(kill)


def face_group(ob, name="__face", eps=2e-5, grow=2):
    """Vertices any shape key moves, grown by a few rings: protected from decimation."""
    kb = ob.data.shape_keys.key_blocks
    base = np.empty(len(ob.data.vertices) * 3)
    kb[0].data.foreach_get("co", base)
    moved = np.zeros(len(ob.data.vertices), bool)
    tmp = np.empty_like(base)
    for k in kb[1:]:
        k.data.foreach_get("co", tmp)
        moved |= np.abs(tmp - base).reshape(-1, 3).max(1) > eps
    adj = [[] for _ in ob.data.vertices]
    for e in ob.data.edges:
        a, b = e.vertices
        adj[a].append(b)
        adj[b].append(a)
    for _ in range(grow):
        nxt = moved.copy()
        for i in np.nonzero(moved)[0]:
            nxt[adj[i]] = True
        moved = nxt
    g = ob.vertex_groups.new(name=name)
    g.add([int(i) for i in np.nonzero(moved)[0]], 1.0, "REPLACE")
    return int(moved.sum())


def nearest_keys(d, src):
    from mathutils.kdtree import KDTree

    sk = src.data.shape_keys
    n = len(src.data.vertices)
    base = np.empty(n * 3)
    sk.key_blocks[0].data.foreach_get("co", base)
    base = base.reshape(-1, 3)
    kd = KDTree(n)
    for i, c in enumerate(base):
        kd.insert(c, i)
    kd.balance()
    m = len(d.data.vertices)
    rest = np.empty(m * 3)
    d.data.vertices.foreach_get("co", rest)
    rest = rest.reshape(-1, 3)
    near = np.array([kd.find(c)[1] for c in rest])
    d.shape_key_add(name="Basis", from_mix=False)
    tmp = np.empty(n * 3)
    for kb in sk.key_blocks[1:]:
        kb.data.foreach_get("co", tmp)
        dl = tmp.reshape(-1, 3)[near] - base[near]
        dl[np.abs(dl).max(1) < 1e-4] = 0
        d.shape_key_add(name=kb.name, from_mix=False).data.foreach_set("co", (rest + dl).ravel())


def decimate_keep_keys(src, target_tris, protect=None):
    """Decimate a copy without shape keys, then rebuild every shape key on the copy by
    binding it to the original with Surface Deform and evaluating each key."""
    d = dup(src, src.name + "_dec", keys=False)
    m = d.modifiers.new("Dec", "DECIMATE")
    m.ratio = min(1.0, target_tris / max(1, tris(d)))
    if protect:
        m.vertex_group = protect
        m.invert_vertex_group = True
        m.vertex_group_factor = 0.9
    apply_first(d, m)
    sk = src.data.shape_keys
    if sk:
        # bind and evaluate in the rest pose: the source is skinned to the rig, and whatever
        # clip the NLA puts on frame 1 would otherwise pose it away from the unskinned copy
        rig.data.pose_position = "REST"
        sd = d.modifiers.new("SD", "SURFACE_DEFORM")
        sd.target = src
        with ctx(d):
            bpy.ops.object.modifier_move_to_index(modifier="SD", index=0)
            bpy.ops.object.surfacedeform_bind(modifier="SD")
        if not sd.is_bound:
            # Surface Deform refused the target ("invalid polygons": the F-16 characters' skin with the cut under
            # their clothes): each vertex takes the offsets of the nearest source vertex instead (the face is
            # protected from decimation, so its vertices stay where they were)
            d.modifiers.remove(sd)
            rig.data.pose_position = "POSE"
            nearest_keys(d, src)
            report.setdefault("keys_by_nearest_vertex", []).append(d.name)
            return d
        d.shape_key_add(name="Basis", from_mix=False)
        dg = bpy.context.evaluated_depsgraph_get()
        arm = d.modifiers.get("Armature")
        if arm:
            arm.show_viewport = False
        for kb in sk.key_blocks:
            kb.value = 0.0
        n = len(d.data.vertices)
        co = np.empty(n * 3)
        rest = np.empty(n * 3)
        d.data.vertices.foreach_get("co", rest)
        for kb in sk.key_blocks[1:]:
            kb.value = 1.0
            dg.update()
            ev = d.evaluated_get(dg)
            ev.data.vertices.foreach_get("co", co)
            # Surface Deform leaves ~1e-6 m noise everywhere; zero it so the exporter can
            # write sparse morph targets (only the vertices a key really moves)
            dl = (co - rest).reshape(-1, 3)
            dl[np.abs(dl).max(1) < 1e-4] = 0
            co = (rest.reshape(-1, 3) + dl).ravel()
            nk = d.shape_key_add(name=kb.name, from_mix=False)
            nk.data.foreach_set("co", co)
            kb.value = 0.0
        dg.update()
        d.modifiers.remove(sd)
        if arm:
            arm.show_viewport = True
        rig.data.pose_position = "POSE"
    return d


def decimate_except(src, target_tris, keep="__keep"):
    """Decimate src to about target_tris but leave the faces whose vertices are all in the vertex group `keep`
    untouched (thin tubes such as straps, knots and ropes, which collapse into flat ribbons): they are split off,
    the rest is decimated to what remains of the budget, and the two are joined again. No shape keys (clothes)."""
    g = src.vertex_groups.get(keep)
    if g is None:
        return decimate_keep_keys(src, target_tris)
    gi = g.index
    rest, kept = dup(src, src.name + "_dec", keys=False), dup(src, src.name + "_keep", keys=False)
    for ob, drop_kept in ((rest, True), (kept, False)):
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        dl = bm.verts.layers.deform.active
        inside = lambda f: all(dl and gi in v[dl] and v[dl][gi] > 0.5 for v in f.verts)  # noqa: E731
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if inside(f) == drop_kept], context="FACES")
        bm.to_mesh(ob.data)
        bm.free()
        ob.data.update()
    m = rest.modifiers.new("Dec", "DECIMATE")
    m.ratio = min(1.0, max(0.05, (target_tris - tris(kept)) / max(1, tris(rest))))
    apply_first(rest, m)
    with bpy.context.temp_override(
        object=rest, active_object=rest, selected_objects=[rest, kept], selected_editable_objects=[rest, kept]
    ):
        bpy.ops.object.join()
    return rest


def moved_verts(ob, eps=1e-4):
    """Boolean per vertex: does any shape key move it (by more than eps metres)?"""
    n = len(ob.data.vertices)
    moved = np.zeros(n, bool)
    sk = ob.data.shape_keys
    if not sk:
        return moved
    kb = sk.key_blocks
    base = np.empty(n * 3)
    kb[0].data.foreach_get("co", base)
    tmp = np.empty_like(base)
    for k in kb[1:]:
        k.data.foreach_get("co", tmp)
        moved |= np.abs(tmp - base).reshape(-1, 3).max(1) > eps
    return moved


def prune_keys(ob, eps=1e-4):
    """Remove shape keys that move nothing on this mesh. three.js keeps every morph target
    of a mesh in one float texture (vertices x targets), so empty ones still cost memory."""
    sk = ob.data.shape_keys
    if not sk:
        return 0
    kb = sk.key_blocks
    n = len(ob.data.vertices)
    base = np.empty(n * 3)
    kb[0].data.foreach_get("co", base)
    tmp = np.empty_like(base)
    dead = []
    for k in kb[1:]:
        k.data.foreach_get("co", tmp)
        if np.abs(tmp - base).max() <= eps:
            dead.append(k.name)
    for name in dead:
        ob.shape_key_remove(kb[name])
    if len(ob.data.shape_keys.key_blocks) == 1:
        ob.shape_key_clear()
    return len(dead)


def split_head(ob, margin=0.02):
    """Cut the skin mesh in two along a horizontal plane under the lowest vertex any shape
    key moves: a small head that keeps the morphs and a body without any. Normals are
    frozen as custom normals first so the cut does not show as a lighting seam.
    Costs one extra mesh (2 draw calls with its shadow) and saves most of the morph memory."""
    me = ob.data
    moved = moved_verts(ob)
    if not moved.any():
        return ob, None
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    z = co.reshape(-1, 3)[:, 2]
    zcut = float(z[moved].min()) - margin
    vn = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("normal", vn)
    vn = [tuple(v) for v in vn.reshape(-1, 3)]
    head = dup(ob, ob.name + "_head")
    body = dup(ob, ob.name + "_body", keys=False)
    for part, keep_head in ((head, True), (body, False)):
        part.data.normals_split_custom_set_from_vertices(vn)  # on the copies: the source is used again
        bm = bmesh.new()
        bm.from_mesh(part.data)
        kill = [f for f in bm.faces if (f.calc_center_median().z > zcut) != keep_head]
        bmesh.ops.delete(bm, geom=kill, context="FACES")
        bm.to_mesh(part.data)
        bm.free()
        part.data.update()
    stray = moved_verts(body).sum() if body.data.shape_keys else 0
    head.name, body.name = "Head", "Body"
    prune_keys(head)
    report.setdefault("head_split", {})[ob.name] = {
        "zcut": round(zcut, 3),
        "head_verts": len(head.data.vertices),
        "body_verts": len(body.data.vertices),
        "stray_moved_in_body": int(stray),
    }
    return body, head


def select_only(objs):
    for o in scene.objects:
        o.select_set(False)
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig


def export(objs, path, morph=True, morph_normal=True, anim=False):
    select_only(objs)
    bpy.ops.export_scene.gltf(
        filepath=path,
        use_selection=True,
        export_format="GLB",
        export_skins=True,
        export_def_bones=True,
        export_rest_position_armature=True,
        export_influence_nb=4,
        export_all_influences=False,
        export_morph=morph,
        export_morph_normal=morph_normal,
        export_morph_tangent=False,
        export_try_sparse_sk=True,
        export_try_omit_sparse_sk=True,
        export_animations=anim,
        export_animation_mode="NLA_TRACKS",
        export_yup=True,
        export_apply=False,
        export_tangents=True,  # gltf-transform prunes them where no normal map
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_cameras=False,
        export_lights=False,
    )
    return os.path.getsize(path)


def atlas_bake(ob, size=1024):
    """Bake every material's base colour into one atlas on a fresh UV layout."""
    me = ob.data
    src_uv = me.uv_layers[0].name
    atlas_uv = me.uv_layers.new(name="atlas")
    me.uv_layers.active = atlas_uv
    for x in scene.objects:
        x.select_set(False)
    ob.hide_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")
    img = bpy.data.images.new(ob.name + "_atlas", size, size)
    for mat in me.materials:
        nt = mat.node_tree
        for n in nt.nodes:
            if n.type == "TEX_IMAGE" and n.image is not img:
                uvn = nt.nodes.new("ShaderNodeUVMap")
                uvn.uv_map = src_uv
                nt.links.new(uvn.outputs["UV"], n.inputs["Vector"])
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = img
        nt.nodes.active = tn
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 4
    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    scene.render.bake.margin = 4
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=4)
    path = os.path.join(outdir, ob.name + "_atlas.png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    mat = bpy.data.materials.new("walk")
    mat.use_nodes = True
    nt = mat.node_tree
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img
    nt.links.new(t.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.75
    me.materials.clear()
    me.materials.append(mat)
    me.uv_layers.remove(me.uv_layers[src_uv])
    me.uv_layers.active = me.uv_layers["atlas"]


def _srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _lin_to_srgb(c):
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 0), 1 / 2.4) - 0.055)


def _base_rgba(ob):
    """The material's base colour image with its tint (Mix multiply) baked in; float RGBA, rows bottom-up."""
    nt = ob.data.materials[0].node_tree
    img = next(
        n.image
        for n in nt.nodes
        if n.type == "TEX_IMAGE" and n.image and n.image.colorspace_settings.name != "Non-Color"
    )
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    for n in nt.nodes:
        if n.type == "MIX" and n.data_type == "RGBA":
            tint = np.array(n.inputs[7].default_value[:3], np.float32)  # the colour B socket
            px[..., :3] = _lin_to_srgb(_srgb_to_lin(px[..., :3]) * tint)
    return px, nt.nodes["Principled BSDF"].inputs["Roughness"].default_value


def _resized(px, s):
    h, w = px.shape[:2]
    tmp = bpy.data.images.new("__tmp", w, h, alpha=True)
    tmp.pixels.foreach_set(px.ravel())
    tmp.scale(s, s)
    out = np.empty(s * s * 4, np.float32)
    tmp.pixels.foreach_get(out)
    bpy.data.images.remove(tmp)
    return out.reshape(s, s, 4)


def _bleed(px):
    """Colour for the see-through texels from the nearest opaque ones (push-pull over a mip pyramid): mipmaps and
    texture compression average the colour of texels round a card's edge, and MPFB leaves whatever colour it had
    there (blue-white on afro01) plus the atlas's black gutters, which showed as blue lines on the hair's edges."""
    a = (px[..., 3] > 0.5).astype(np.float32)
    levels = [(px[..., :3] * a[..., None], a)]
    while min(levels[-1][1].shape) > 1:
        c, w = levels[-1]
        h2, w2 = c.shape[0] // 2, c.shape[1] // 2
        levels.append(
            (
                c[: h2 * 2, : w2 * 2].reshape(h2, 2, w2, 2, 3).sum((1, 3)),
                w[: h2 * 2, : w2 * 2].reshape(h2, 2, w2, 2).sum((1, 3)),
            )
        )
    c, w = levels[-1]
    fill = c / np.maximum(w, 1e-6)[..., None]
    for c, w in reversed(levels[:-1]):
        up = np.repeat(np.repeat(fill, 2, 0), 2, 1)
        up = np.pad(up, ((0, c.shape[0] - up.shape[0]), (0, c.shape[1] - up.shape[1]), (0, 0)), mode="edge")
        fill = np.where(w[..., None] > 0, c / np.maximum(w, 1e-6)[..., None], up)
    out = px.copy()
    out[..., :3] = np.where(a[..., None] > 0, px[..., :3], fill)
    return out


def merge_parts(objs, name, layout, size, alpha):
    """Join several small parts into one mesh with one material: their base colour images
    (tints baked in) go into one atlas and the UVs are moved into each part's square.
    layout: (x0, y0, side) in atlas pixels, origin bottom-left, one per object.
    Shape keys survive the join (matched by name; parts without keys get the basis)."""
    W, H = size
    atlas = np.zeros((H, W, 4), np.float32)
    rough = []
    parts = [dup(ob, ob.name + "_m") for ob in objs]
    spec = objs[0].data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value
    for ob, (x0, y0, s) in zip(parts, layout):
        px, r = _base_rgba(ob)
        rough.append(r)
        atlas[y0 : y0 + s, x0 : x0 + s] = _resized(px, s)
        uvl = ob.data.uv_layers[0]
        uv = np.empty(len(uvl.data) * 2)
        uvl.data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2)
        uv[:, 0] = (x0 + uv[:, 0] * s) / W
        uv[:, 1] = (y0 + uv[:, 1] * s) / H
        uvl.data.foreach_set("uv", uv.ravel())
    if not alpha:
        atlas[..., 3] = 1.0
    else:
        atlas = _bleed(atlas)
    img = bpy.data.images.new(name + "_atlas", W, H, alpha=True)
    img.pixels.foreach_set(atlas.ravel())
    img.filepath_raw = os.path.join(outdir, name + "_atlas.png")
    img.file_format = "PNG"
    img.save()
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img
    nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    if alpha:
        # alpha = 1 - (a < cutoff): the node pattern the glTF exporter writes as alphaMode MASK (a texture
        # linked straight into Alpha exports as BLEND, which three.js sorts and draws without depth writes)
        lt = nt.nodes.new("ShaderNodeMath")
        lt.operation = "LESS_THAN"
        lt.inputs[1].default_value = ALPHA_CUTOFF
        inv = nt.nodes.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        nt.links.new(t.outputs["Alpha"], lt.inputs[0])
        nt.links.new(lt.outputs[0], inv.inputs[1])
        nt.links.new(inv.outputs[0], bsdf.inputs["Alpha"])
    # the first part's: the hair (brows and lashes are a few cards; their mean made the hair shinier than melos_prep set)
    bsdf.inputs["Roughness"].default_value = float(rough[0])
    bsdf.inputs["Specular IOR Level"].default_value = spec
    for ob in parts:
        ob.data.materials.clear()
        ob.data.materials.append(mat)
    keyed = [p for p in parts if p.data.shape_keys] or parts
    active = keyed[0]
    with bpy.context.temp_override(
        object=active, active_object=active, selected_objects=parts, selected_editable_objects=parts
    ):
        bpy.ops.object.join()
    active.name = name.capitalize()
    return active


ALPHA_CUTOFF = 0.35  # hair cards: low enough to keep the thin strand ends
TEETH_HIGH = 2400  # tris; the MPFB teeth are 7.1k, which alone would push talk_high past 40k
# hair cards: hair 752 + brows and lashes 240 each, 16 px gutters; mouth: teeth and tongue side by side
HAIR_LAYOUT = ((1024, 1024), [(0, 0, 752), (768, 0, 240), (768, 272, 240)])
MOUTH_LAYOUT = ((1024, 512), [(0, 0, 496), (512, 0, 496)])


def main():
    anims.build(rig)
    o = {n: bpy.data.objects[n] for n in TALK + ["EyesLow"]}

    # 8 parts -> 5 materials (skin, eyes, hair cards, clothes, teeth): art-direction 9.2
    hair = merge_parts([o["Hair"], o["Brows"], o["Lashes"]], "hair", HAIR_LAYOUT[1], HAIR_LAYOUT[0], True)
    teeth_h = decimate_keep_keys(o["Teeth"], TEETH_HIGH) if tris(o["Teeth"]) > TEETH_HIGH else o["Teeth"]
    mouth = merge_parts([teeth_h, o["Tongue"]], "teeth", MOUTH_LAYOUT[1], MOUTH_LAYOUT[0], False)
    report["merged"] = {"hair": tris(hair), "teeth": tris(mouth)}

    for part in (hair, mouth):
        report.setdefault("pruned_keys", {})[part.name] = prune_keys(part)

    # ---------- high: the build as is, skin cut into head (morphs) + body (none); the skin the tunic
    # covers goes here too, or it pokes through the cloth when he moves (UX round 4)
    body_hi = dup(o["Body"], "Body_high")
    report["under_tunic_deleted_high"] = delete_group(body_hi, "__under_tunic")
    body_h, head_h = split_head(body_hi)
    for part in (body_h, head_h):
        drop_islands(part)
    high = [body_h, head_h, o["Eyes"], hair, mouth, o["Tunic"]]
    report["talk_high"] = {"tris": sum(tris(x) for x in high), "parts": {x.name: tris(x) for x in high}}
    report["talk_high"]["bytes"] = export(high, os.path.join(outdir, "talk_high.glb"))
    report["talk_high"]["bytes_no_morph_normals"] = export(
        high, os.path.join(outdir, "talk_high_nomn.glb"), morph_normal=False
    )

    # ---------- standard
    body = dup(o["Body"], "Body_std")
    report["under_tunic_deleted"] = delete_group(body, "__under_tunic")
    report["face_verts"] = face_group(body)
    body_s = decimate_keep_keys(body, 15500, protect="__face")
    teeth_s = decimate_keep_keys(o["Teeth"], 2000)
    tunic_s = decimate_except(o["Tunic"], 5000)  # its straps, knots and rope (__keep) are not decimated
    mouth_s = merge_parts([teeth_s, o["Tongue"]], "teeth", MOUTH_LAYOUT[1], MOUTH_LAYOUT[0], False)
    report["pruned_keys"]["teeth_std"] = prune_keys(mouth_s)
    drop_islands(body_s)
    body_ss, head_s = split_head(body_s)
    std = [body_ss, head_s, o["Eyes"], hair, mouth_s, tunic_s]
    report["talk_std"] = {"tris": sum(tris(x) for x in std), "parts": {x.name: tris(x) for x in std}}
    report["talk_std"]["bytes"] = export(std, os.path.join(outdir, "talk_std.glb"))
    report["talk_std"]["bytes_no_morph_normals"] = export(
        std, os.path.join(outdir, "talk_std_nomn.glb"), morph_normal=False
    )

    # ---------- walk: one mesh, 8k, one material
    parts = [
        dup(body, "w_body", keys=False),
        dup(o["Tunic"], "w_tunic", keys=False),
        dup(o["Hair"], "w_hair", keys=False),
        dup(o["EyesLow"], "w_eyes", keys=False),
    ]
    drop_islands(parts[0])
    for p in parts:
        for g in list(p.vertex_groups):
            if g.name.startswith("__"):
                p.vertex_groups.remove(g)
    with bpy.context.temp_override(
        object=parts[0], active_object=parts[0], selected_objects=parts, selected_editable_objects=parts
    ):
        bpy.ops.object.join()
    walk = parts[0]
    walk.name = "Walk"
    m = walk.modifiers.new("Dec", "DECIMATE")
    m.ratio = 8000 / tris(walk)
    apply_first(walk, m)
    atlas_bake(walk)
    report["walk"] = {"tris": tris(walk), "materials": len(walk.data.materials)}
    report["walk"]["bytes"] = export([walk], os.path.join(outdir, "walk.glb"), morph=False)

    # ---------- shared clips
    report["anims"] = {
        "bytes": export([], os.path.join(outdir, "anims.glb"), morph=False, anim=True),
        "bones": len(rig.data.bones),
        "clips": anims.REPORT or "procedural placeholders",
    }
    report["morphs"] = len(o["Body"].data.shape_keys.key_blocks) - 1
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(outdir, "lods.blend"))
    import json

    with open(os.path.join(outdir, "lod_report.json"), "w") as f:
        json.dump(report, f, indent=1)
    print(json.dumps(report, indent=1))


main()
