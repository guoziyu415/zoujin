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
- Hair (v3, UX round 2): warm dark brown, its outline pushed out in soft clumps about 2 cm across (small curls
  instead of a smooth helmet). Round 4: 1 cm thinner on top, still round; a few of the front cards copied smaller
  onto the forehead and temples, so the hairline is no longer a straight line; the scalp tinted after the AO bake,
  to the hair's colour a little darker (the roots), since between the cards it showed reddish and lighter than them.
  Round 5: three curls on the forehead, each tapering to a point, with a small contact shadow painted at its root.
- Brows (round 5): graded to the hair's colour as drawn (every texel past the alpha cut); graded on the dense middle
  only, as the hair is, they showed three times lighter than the hair.
- Specular: the tunic and the hair reflect half as much at grazing angles (KHR_materials_specular 0.5); at the
  default the bands and the card edges caught the blue sky as a rim (UX round 4). The tunic is fully rough.
- Dust from a day on the road, by height on the body: feet and shins below the knee, the tunic's hem, the sandals.
  The tunic's shoulders are faded by the sun where the cloth faces up.
- Skin normal map (new in v2; compress.mjs keeps it at 2048 on the high tier and 1024 on std): the larger relief in
  the colour map's own detail (a band-pass of its luminance). No pores (art-direction 5.1).
- Ambient occlusion baked with Cycles (rest pose, the whole figure as occluder) and multiplied into the skin and
  tunic colour maps: contact shadow under the rope, the bands, the bundle and the tunic's edges, and in the folds.
  Not on the bands, rope and sandals themselves: their pieces share UV space, so one bake would land on another.
- Roughness per part (MPFB sets 0.7 everywhere); materials renamed as on the stand-in (skin, eyes, hair, ...):
  compress.mjs and the test page find the skin and the alpha-tested parts by material name.
- Tunic: the wool (torso and skirt) unwrapped again, angle-based with a seam down his right side, and fitted into its
  UV region: it came from the MPFB helper garments, whose UVs sit in a sliver of the body atlas, so v1 and v2 showed
  one flat texel of the wool texture (no weave, no fading, no AO). Then tunic_base.png and tunic_nrm.png from
  melos_tex.py (UV regions of melos_clothes_v2), packed into the file; triangulated (the sole hulls are n-gons, and
  the exporter cannot compute tangents for the normal map on those).
- Tunic folds (UX round 4): a height field over the wool's 3D surface, with folds the way it hangs: fanning out from
  the knot on his left shoulder down to his right hip, soft and horizontal where it bags over the rope, vertical in
  the skirt, gathered under the rope and deepest at the hem. Turned into a normal map in the wool's UV space (slopes
  measured on the cloth, so the unwrap's stretching doesn't matter), blended (UDN) with melos_tex's weave; the
  valleys a little darker in the colour map, so the folds still read on tier B's 512 normal map.
- Bundle, bands and rope graded to UX round 4's mean colours (melos_tex.PART_MEAN) after the dust and AO.
- Image paths cut down to the file name (the Mac build recorded absolute paths with the user name; the pixels are
  packed), then unused data purged.
"""

import math
import os
import sys

import bpy
import bmesh  # noqa: I001  (only importable after bpy)
from mathutils import Vector
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from mathutils import Quaternion
from mathutils.bvhtree import BVHTree

from melos_clothes_v2 import AXIS_Y, HEM_Z, KNEE_Z, NEW_UV, UV_MARGIN
from melos_tex import PART_MEAN, match_mean

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
    "Hair": 0.9,  # dark cards at 0.5 mirrored the blue sky in patches, at 0.7-0.8 still a blue edge against the sky
    "Brows": 0.6,
    "Lashes": 0.6,
    "Tunic": 1.0,  # UX round 4: 0.9-1.0, wool has no sheen
}
# Principled "Specular IOR Level": 0.25 exports as KHR_materials_specular 0.5, half the reflection at grazing angles
SPECULAR = {"Hair": 0.25, "Tunic": 0.25}
MAT_NAME = {"Body": "skin", "Eyes": "eyes", "EyesLow": "eyes", "Teeth": "teeth", "Tongue": "tongue", "Hair": "hair"}
MAT_NAME |= {"Brows": "brows", "Lashes": "lashes", "Tunic": "tunic"}
SKIN = (138, 90, 60)  # #8A5A3C
SKIN_SAT = 0.85
HAIR = (60, 40, 26)  # warm dark brown (UX round 2: warmer than v2's near black)
DUST = (152, 134, 110)
SUN_FADED = (196, 160, 116)
AO = {"Body": (0.5, 0.06), "Tunic": (0.85, 0.08)}  # strength, distance (m)
HAIR_DROP = 0.010  # m off the top (UX round 4)
HAIR_CURLS = 3  # cards copied onto the forehead (UX round 5: two or three)
CURL_X = 0.05  # across the forehead only, not the temples
CURL_TAPER = 0.75  # how far a curl's lower corners are drawn together
CURL_ROOT_R, CURL_ROOT_DARK = 0.002, 0.35  # the contact shadow at a curl's root: radius (m), darkening at its middle
ROOTS = 0.8  # the scalp: the hair's mean colour times this
FOLD_DARK = 0.1  # fold valleys in the colour map
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
    if ob.name in SPECULAR:
        bsdf.inputs["Specular IOR Level"].default_value = SPECULAR[ob.name]
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


def hair_clumps(ob, amp=0.007, cell=0.022):
    """Soft lumps on the hair's outline (UX round 2): afro01's cards sit on a smooth cap that reads as a helmet;
    pushed out from the head's middle in clumps about 2 cm across, the outline breaks up into small curls."""
    from mathutils import noise

    me = ob.data
    centre = sum((v.co for v in me.vertices), Vector()) / len(me.vertices)
    offs = []
    for v in me.vertices:
        n = noise.noise(v.co / cell, noise_basis="PERLIN_ORIGINAL")
        offs.append((v.co - centre).normalized() * amp * max(0.0, 1.6 * n + 0.25))
    blocks = list(me.shape_keys.key_blocks) if me.shape_keys else []
    for kb in blocks:
        for d, o in zip(kb.data, offs):
            d.co += o
    for v, o in zip(me.vertices, offs):
        v.co += o
    me.update()
    return round(max(o.length for o in offs), 4)


def scalp_tint(ob, skin, hair, amount=0.95, soft=10):
    """Paint the skin texture under the scalp group towards the hair's mean opaque colour, a little darker."""
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
    colour = hp[hp[:, 3] > 0.9, :3].mean(0) * ROOTS
    px = image_pixels(skin)  # rows bottom-up, like the UV v axis drawn above
    px[..., :3] = px[..., :3] * (1 - m) + colour * m
    skin.pixels.foreach_set(px.ravel())
    skin.pack()
    return faces


def _skin_bvh(body):
    me = body.data
    return BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])


def hair_thin_top(hair, body, z0, drop=HAIR_DROP):
    """UX round 4: the hair `drop` lower on top and still round. Above z0 (the eyes) every vertex moves towards the
    scalp, the more the higher it sits, so the hair gets thinner on top instead of flatter."""
    bvh = _skin_bvh(body)
    me = hair.data
    co = np.array([v.co[:] for v in me.vertices])
    near = np.array([bvh.find_nearest(Vector(c))[0][:] for c in co])
    top = float(co[:, 2].max())
    w = np.clip((co[:, 2] - z0) / (top - z0), 0, 1)
    w = w * w * (3 - 2 * w)
    lo, hi = 0.0, 1.0
    for _ in range(30):
        pull = (lo + hi) / 2
        new = near + (co - near) * (1 - pull * w)[:, None]
        lo, hi = (pull, hi) if new[:, 2].max() > top - drop else (lo, pull)
    for kb in list(me.shape_keys.key_blocks) if me.shape_keys else []:
        for d, a, b in zip(kb.data, co, new):
            d.co += Vector(b - a)
    me.vertices.foreach_set("co", new.ravel())
    me.update()
    return {"top": round(top, 4), "top_after": round(float(new[:, 2].max()), 4), "pull": round(pull, 3)}


def hairline_curls(hair, body, eye, tex, n=HAIR_CURLS, seed=11):
    """UX round 4: the cards' lower edge drew a straight line across the forehead. A few of the lowest cards along it
    are copied, half the size, a little lower on the forehead, turned at random about the skin's normal: an uneven
    hairline. Round 5: three of them, one each on the left, middle and right of the forehead (a stray one on the
    temple read as a scratch); each tapers to a point (its lower corners drawn together), so the end fades out
    instead of stopping blunt. Corners kept 3 mm off the skin (it moves with the brows, the hair doesn't). Returns
    the root of each (where it leaves the hairline), for root_shadows(). Of the lowest cards in each strip, the one
    with the most hair drawn on it (alpha past the cut): a sparse one showed as a faint dash under a root shadow that
    read as a mole."""
    bvh = _skin_bvh(body)
    rng = np.random.default_rng(seed)
    bm = bmesh.new()
    bm.from_mesh(hair.data)
    uvl = bm.loops.layers.uv.active
    alpha = image_pixels(tex)[..., 3]  # rows bottom-up, like v
    th, tw = alpha.shape

    def drawn(f):
        uv = [lp[uvl].uv for lp in f.loops]
        if len(uv) != 4:
            return 0.0
        s = np.linspace(0.1, 0.9, 7)
        pts = [(uv[0] * (1 - a) + uv[1] * a) * (1 - b) + (uv[3] * (1 - a) + uv[2] * a) * b for a in s for b in s]
        return float(np.mean([alpha[min(th - 1, int(p.y * th)) % th, min(tw - 1, int(p.x * tw)) % tw] > 0.5 for p in pts]))

    cards = [f for f in bm.faces if all(len(e.link_faces) == 1 for e in f.edges)]
    cen = np.array([f.calc_center_median()[:] for f in cards])
    idx = np.flatnonzero((cen[:, 1] < eye[1] + 0.05) & (np.abs(cen[:, 0]) < CURL_X))
    strips = np.digitize(cen[idx, 0], np.linspace(-CURL_X, CURL_X, n + 1)[1:-1])
    pick = []
    for b in range(n):
        mine = idx[strips == b]
        if len(mine):
            low = mine[np.argsort(cen[mine, 2])[:4]]
            pick.append(int(max(low, key=lambda i: drawn(cards[i]))))
    scores = [round(drawn(cards[i]), 2) for i in pick]
    lowest, roots = [], []
    for i in pick:
        c = Vector(cen[i])
        _, n0, _, d0 = bvh.find_nearest(c)
        q1, n1, _, _ = bvh.find_nearest(c - Vector((0, 0, rng.uniform(0.003, 0.008))))
        rot = Quaternion(n1, rng.uniform(-0.6, 0.6)) @ n0.rotation_difference(n1)
        size = rng.uniform(0.45, 0.6)
        centre = q1 + n1 * min(d0, 0.008)
        verts = [g for g in bmesh.ops.duplicate(bm, geom=[cards[i]])["geom"] if isinstance(g, bmesh.types.BMVert)]
        for v in verts:
            v.co = centre + rot @ ((v.co - c) * size)
        # the tip: the two lowest corners drawn most of the way together
        low = sorted(verts, key=lambda v: v.co.z)[:2]
        mid = (low[0].co + low[1].co) / 2
        for v in low:
            v.co = mid + (v.co - mid) * (1 - CURL_TAPER)
        lift = 0.0
        for v in verts:
            q, nq, _, _ = bvh.find_nearest(v.co)
            lift = max(lift, 0.003 - (v.co - q).dot(nq))
        for v in verts:
            v.co += n1 * lift
        lowest.append(min(v.co.z for v in verts))
        top = sorted(verts, key=lambda v: -v.co.z)[:2]
        roots.append(bvh.find_nearest((top[0].co + top[1].co) / 2)[0])
    bm.to_mesh(hair.data)
    bm.free()
    hair.data.update()
    return {"cards": len(lowest), "lowest_z": round(min(lowest), 4), "drawn": scores}, roots


def root_shadows(body, skin, roots, radius=CURL_ROOT_R, dark=CURL_ROOT_DARK):
    """A little contact shadow on the skin where each forehead curl leaves the hairline (UX round 5: 1-2 mm): the
    colour map darkened in a soft spot round each root."""
    bvh = _skin_bvh(body)
    me = body.data
    uvl = me.uv_layers[0].data
    w, h = skin.size
    px = image_pixels(skin)  # rows bottom-up, like the UV v axis
    yy, xx = np.mgrid[0:h, 0:w]
    done = 0
    for r in roots:
        _, _, fi, _ = bvh.find_nearest(r)
        p = me.polygons[fi]
        co = [me.vertices[i].co for i in p.vertices]
        uv = [Vector(uvl[i].uv) for i in p.loop_indices]
        wts = [1.0 / max(1e-5, (c - r).length) for c in co]
        at = sum((u * k for u, k in zip(uv, wts)), Vector((0, 0))) / sum(wts)
        uv_area = abs(sum(uv[k].x * uv[(k + 1) % len(uv)].y - uv[(k + 1) % len(uv)].x * uv[k].y
                          for k in range(len(uv)))) / 2
        texels_per_m = math.sqrt(uv_area * w * h / max(p.area, 1e-9))
        rad = max(1.5, radius * texels_per_m)
        d2 = ((xx - at.x * w) ** 2 + (yy - at.y * h) ** 2) / rad**2
        m = (np.exp(-2 * d2) * dark)[..., None]
        px[..., :3] *= 1 - m
        done += 1
    skin.pixels.foreach_set(px.ravel())
    skin.pack()
    return done


def wool_uv(ob):
    """Unwrap the torso and skirt (the faces in the wool region) and fit them into it at one texel density."""
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    ob.select_set(True)
    vl.objects.active = ob
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    uvl = bm.loops.layers.uv.active

    def wool(f):
        return bool(in_region(np.mean([lp[uvl].uv[:] for lp in f.loops], axis=0), "wool"))

    faces = [f for f in bm.faces if wool(f)]
    geom = list({v for f in faces for v in f.verts}) + list({e for f in faces for e in f.edges}) + faces
    # seam down his right side, where the skirt's slit already is (the torso is a closed tube until cut there)
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, AXIS_Y, 0), plane_no=(0, 1, 0), dist=1e-5)
    for e in bm.edges:
        e.seam = all(v.co.x < 0 and abs(v.co.y - AXIS_Y) < 1e-4 for v in e.verts) and any(map(wool, e.link_faces))
    for f in bm.faces:
        f.select_set(wool(f))
    bm.to_mesh(ob.data)
    bm.free()
    with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.02)
        bpy.ops.object.mode_set(mode="OBJECT")
    loops = [i for p in ob.data.polygons if p.select for i in p.loop_indices]
    uv = ob.data.uv_layers.active.data
    xy = np.array([uv[i].uv[:] for i in loops])
    lo, span = xy.min(0), np.ptp(xy, axis=0)
    u0, u1, v0, v1 = NEW_UV["wool"]
    k = min((u1 - u0 - 2 * UV_MARGIN) / span[0], (v1 - v0 - 2 * UV_MARGIN) / span[1])
    for i, (x, y) in zip(loops, (xy - lo) * k + (u0 + UV_MARGIN, v0 + UV_MARGIN)):
        uv[i].uv = (x, y)
    sel = [p for p in ob.data.polygons if p.select]
    uv_area = sum(_shoelace(np.array([uv[i].uv[:] for i in p.loop_indices])) for p in sel)
    return {"faces": len(faces), "px_per_cm": round(float(1024 * np.sqrt(uv_area / sum(p.area for p in sel)) / 100), 1)}


def _shoelace(q):
    return abs(np.dot(q[:, 0], np.roll(q[:, 1], -1)) - np.dot(q[:, 1], np.roll(q[:, 0], -1))) / 2


def _value_noise(p, cell, seed):
    """Smooth 3D value noise, -1..1, at the points p (n x 3, metres)."""
    g = np.random.default_rng(seed).uniform(-1, 1, (64, 64, 64)).astype(np.float32)
    q = p / cell
    i = np.floor(q).astype(int)
    f = q - i
    f = f * f * (3 - 2 * f)
    out = np.zeros(len(p), np.float32)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = np.prod([f[:, k] if d else 1 - f[:, k] for k, d in enumerate((dx, dy, dz))], axis=0)
                out += w * g[(i[:, 0] + dx) % 64, (i[:, 1] + dy) % 64, (i[:, 2] + dz) % 64]
    return out


def wool_positions(ob, size):
    """Each wool texel's point on the cloth, and which texels the wool covers (rows bottom-up, like image_pixels)."""
    uvl = ob.data.uv_layers[0].data
    mw = ob.matrix_world
    co = np.array([(mw @ v.co)[:] for v in ob.data.vertices])
    pos = np.zeros((size, size, 3), np.float32)
    cover = np.zeros((size, size), bool)
    for p in ob.data.polygons:
        if not in_region(uv_centre(ob, p), "wool"):
            continue
        vi = list(p.vertices)
        uv = np.array([uvl[i].uv[:] for i in p.loop_indices]) * size - 0.5  # texel centres on the integers
        for k in range(1, len(vi) - 1):
            a, b, c = uv[0], uv[k], uv[k + 1]
            (x0, y0), (x1, y1) = np.floor(np.min([a, b, c], 0)).astype(int), np.ceil(np.max([a, b, c], 0)).astype(int)
            x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, size - 1), min(y1, size - 1)
            m = np.array([b - a, c - a]).T
            if x1 < x0 or y1 < y0 or abs(np.linalg.det(m)) < 1e-12:
                continue
            ys, xs = np.mgrid[y0 : y1 + 1, x0 : x1 + 1]
            xy = np.stack([xs.ravel(), ys.ravel()], -1).astype(float)
            l12 = np.linalg.solve(m, (xy - a).T).T
            l0 = 1 - l12.sum(1)
            inside = (l0 >= -1e-6) & (l12 >= -1e-6).all(1)
            pts = l0[inside, None] * co[vi[0]] + l12[inside, :1] * co[vi[k]] + l12[inside, 1:] * co[vi[k + 1]]
            yy, xx = xy[inside, 1].astype(int), xy[inside, 0].astype(int)
            pos[yy, xx], cover[yy, xx] = pts, True
    return pos, cover


def tunic_folds(ob, base, nrm_in, nrm_out):
    """The folds' height field over the wool (see the module notes), written into a copy of nrm_in at nrm_out;
    the valleys darkened in base. Returns numbers for the report."""
    size = base.size[0]
    pos, cover = wool_positions(ob, size)
    co = np.array([v.co[:] for v in ob.data.vertices])
    in_part = {n: sorted({i for p in ob.data.polygons if in_region(uv_centre(ob, p), n) for i in p.vertices})
               for n in ("wool", "rope")}
    wool = co[in_part["wool"]]
    band = wool[(wool[:, 0] > 0.11) & (wool[:, 0] < 0.17)]
    knot = band[np.argmax(band[:, 2])]  # where melos_clothes_v4 ties the knot on his left shoulder
    rope_z = float(co[in_part["rope"], 2].mean())
    p = pos[cover]
    x, y, z = p.T
    n1, n2 = _value_noise(p, 0.05, 1), _value_noise(p, 0.12, 2)
    # from the knot down across to his right hip, front and back; finer near the knot, as fanned folds are
    dx, dz = x - knot[0], z - knot[2]
    r, th = np.hypot(dx, dz), np.arctan2(dz, dx)
    toward = np.clip(np.cos(th - np.arctan2(-1.0, -0.75)), 0, 1) ** 2
    reach = np.clip((r - 0.02) / 0.06, 0, 1) * np.clip((0.55 - r) / 0.2, 0, 1)
    above = np.clip((z - rope_z - 0.02) / 0.05, 0, 1)
    h = 0.0035 * toward * reach * above * np.sin(24 * th + 1.2 * n1)
    # bagging over the rope: soft and horizontal
    t = z - rope_z
    blouse = np.clip((t - 0.005) / 0.02, 0, 1) * np.clip((0.10 - t) / 0.04, 0, 1)
    h += 0.0022 * blouse * np.sin(2 * np.pi * t / 0.032 + 1.5 * n2)
    # the skirt: vertical, gathered under the rope and deepest at the hem (26 round him, so no step at the seam)
    phi = np.arctan2(y - AXIS_Y, x)
    hem = np.clip((HEM_Z + 0.22 - z) / 0.18, 0, 1)
    gather = np.clip((-t - 0.015) / 0.02, 0, 1) * np.clip((t + 0.14) / 0.06, 0, 1)
    h += (t < -0.01) * (0.0032 * hem + 0.0018 * gather) * np.sin(26 * phi + 2.0 * n2 + 0.6 * n1)
    H = np.zeros((size, size), np.float32)
    H[cover] = h

    def slope(ax):
        """dH/ds along a texel axis, s measured on the cloth: central where both neighbours are wool, else one-sided"""
        f, b = np.roll(H, -1, ax), np.roll(H, 1, ax)
        pf, pb = np.roll(pos, -1, ax), np.roll(pos, 1, ax)
        cf, cb = np.roll(cover, -1, ax), np.roll(cover, 1, ax)
        both = cf & cb
        dh = np.where(both, f - b, np.where(cf, f - H, H - b))
        ds = np.linalg.norm(np.where(both[..., None], pf - pb, np.where(cf[..., None], pf - pos, pos - pb)), axis=-1)
        return np.where(cover & (cf | cb), dh / np.maximum(ds, 1e-5), 0)

    fold = np.stack([-slope(1), -slope(0)], -1)  # x is +u, rows bottom-up are +v (OpenGL, as glTF)
    have = cover.copy()
    for _ in range(4):  # into the gutters, so mipmaps don't pull flat normals over the islands' edges
        acc, cnt = np.zeros_like(fold), np.zeros((size, size), np.float32)
        for ax in (0, 1):
            for sh in (1, -1):
                acc += np.roll(fold * have[..., None], sh, ax)
                cnt += np.roll(have, sh, ax)
        grow = ~have & (cnt > 0)
        fold[grow] = acc[grow] / cnt[grow, None]
        have |= grow
    nw = np.asarray(Image.open(nrm_in).convert("RGB"), np.float32)[::-1] / 255 * 2 - 1
    n = np.concatenate([nw[..., :2] + fold, nw[..., 2:]], -1)  # UDN blend
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    Image.fromarray(((n[::-1] * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8), "RGB").save(nrm_out)
    px = image_pixels(base)
    dark = 1 - FOLD_DARK * np.clip(-H / 0.0035, 0, 1)
    px[..., :3] = to_srgb(to_lin(px[..., :3]) * dark[..., None])
    base.pixels.foreach_set(px.ravel())
    lean = np.degrees(np.arctan(np.linalg.norm(fold[cover], axis=-1)))
    return {"knot": [round(float(c), 3) for c in knot], "rope_z": round(rope_z, 3), "texels": int(cover.sum()),
            "fold_lean_deg_p50_p99": [round(float(np.percentile(lean, q)), 1) for q in (50, 99)]}


def grade_parts(ob, img):
    """The bundle, bands and rope back to UX round 4's mean colours (PART_MEAN) after the dust and AO."""
    px = image_pixels(img)
    out = {}
    for name, target in PART_MEAN.items():
        sel = face_mask(ob, img, lambda p, n=name: 1.0 if in_region(uv_centre(ob, p), n) else None, 0) > 0.5
        rgb = match_mean(px[..., :3][sel], target)
        px[..., :3][sel] = rgb
        out[name] = [round(float(c) * 255) for c in rgb.mean(0)]
    img.pixels.foreach_set(px.ravel())
    return out


def tunic_textures(ob):
    nt = ob.data.materials[0].node_tree
    bsdf = nt.nodes["Principled BSDF"]
    base = bpy.data.images.load(os.path.join(tex_dir, "tunic_base.png"))
    nrm_path = os.path.join(os.path.dirname(os.path.abspath(out)), "tunic_nrm.png")
    report["tunic_folds"] = tunic_folds(ob, base, os.path.join(tex_dir, "tunic_nrm.png"), nrm_path)
    nrm = bpy.data.images.load(nrm_path)
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
    # AO only where every texel belongs to one surface: the two bands and the knot share their region, as do the rope
    # and its ends and the two sandals, so their bakes overwrite each other (a band's inside showed on its outside)
    size = base.size[0]
    v, u = (np.mgrid[0:size, 0:size] + 0.5) / size  # rows bottom-up, like image_pixels
    own = np.zeros((size, size), np.float32)
    for name, k in (("wool", 1.0), ("bundle", 0.55)):  # the bundle's contact with the back and its knot left dark stains
        u0, u1, v0, v1 = NEW_UV[name]
        own[(u >= u0) & (u < u1) & (v >= v0) & (v < v1)] = k
    # the layers behind the rope (melos_clothes_v5.py marks them): hidden at bake time, their AO is nearly black, and
    # where they come through the skirt top in a pose they made a dark band under the rope (UX round 5, item 2). They
    # take the skirt's colour
    attr = ob.data.attributes.get("__inner")
    if attr is not None:
        flags = np.zeros(len(ob.data.polygons), np.int32)
        attr.data.foreach_get("value", flags)
        inner = face_mask(ob, base, lambda p: 1.0 if flags[p.index] else None, 1)
        own *= 1.0 - inner
        report["tunic_inner_faces"] = int(flags.sum())
    darken(base, bake_ao(ob, size, AO["Tunic"][1]), AO["Tunic"][0] * own)
    report["part_means"] = grade_parts(ob, base)
    for img in (base, nrm):
        img.pack()
    nt.nodes["tunic_tex"].image = base
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = nrm
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(t.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = ROUGH["Tunic"]
    bsdf.inputs["Specular IOR Level"].default_value = SPECULAR["Tunic"]
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(ob.data)
    bm.free()
    # the strands, knots, rope and sandal straps are thin tubes of a few sides: lod_export leaves the vertices in
    # "__keep" out of decimation (talk_std halved them into flat ribbons), so tier B takes its cut from the wool
    keep = ob.vertex_groups.new(name="__keep")
    thin = {i for p in ob.data.polygons if any(in_region(uv_centre(ob, p), n) for n in ("bands", "rope", "straps", "soles"))
            for i in p.vertices}
    keep.add(sorted(thin), 1.0, "REPLACE")


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
report["hair_gain"] = grade(img["Hair"], image_pixels(img["Hair"])[..., 3] > 0.9, HAIR)
# the brows the hair's colour as it is drawn (UX round 5: they read three times lighter than the hair): what shows is
# every texel past the alpha cut, not only the dense middle the hair grade looks at
hp = image_pixels(img["Hair"])
hair_drawn = tuple(float(x) for x in (to_srgb(to_lin(hp[hp[..., 3] > 0.5, :3]).mean(0)) * 255))
report["brows_gain"] = grade(img["Brows"], image_pixels(img["Brows"])[..., 3] > 0.5, hair_drawn)
report["brows_target"] = [round(x) for x in hair_drawn]
nrm_path = os.path.join(os.path.dirname(os.path.abspath(out)), "skin_nrm.png")
cover = face_mask(body, skin, lambda p: 1.0, 0)[::-1] > 0.5
report["skin_normal_lean_deg"] = skin_normal(skin, nrm_path, cover)
attach_normal(body, nrm_path)
report["hair_clumps_max_m"] = hair_clumps(OBJ["Hair"])
eye = np.mean([v.co[:] for v in OBJ["Eyes"].data.vertices], axis=0)
report["hair_top"] = hair_thin_top(OBJ["Hair"], body, float(eye[2]))
report["hair_curls"], curl_roots = hairline_curls(OBJ["Hair"], body, eye, img["Hair"])
bz = z_of(body)
legs = face_mask(body, skin, lambda p: 0.5 * np.clip((KNEE_Z - bz[list(p.vertices)].mean()) / 0.42, 0, 1) ** 0.8, 6)
mix_towards(skin, legs, DUST)
OBJ["EyesLow"].hide_render = True  # the low eyes sit in the same place as the high ones
darken(skin, bake_ao(body, min(2048, skin.size[0]), AO["Body"][1]), AO["Body"][0])
OBJ["EyesLow"].hide_render = False
report["scalp_faces"] = scalp_tint(body, skin, img["Hair"])  # after the AO: the hair's cards darkened it unevenly
report["curl_root_shadows"] = root_shadows(body, skin, curl_roots)
skin.pack()
report["wool_uv"] = wool_uv(OBJ["Tunic"])
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
