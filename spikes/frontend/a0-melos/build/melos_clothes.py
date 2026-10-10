"""Melos's exomis, belt and sandals, cut out of the MPFB helper garments (A-0 step 2).

Runs inside Blender on the Mac (through the Blender MCP, or `blender -b melos.blend --python`), after the human,
the game_engine rig and the face targets exist (build_melos.py).  MPFB's system assets have no ancient clothes,
so the tunic is made from the basemesh's own helper garments, which already carry the rig weights:
- torso: `helper-tights` between the belt and the neck, sleeveless, cut diagonally so the right shoulder and the
  right side of the chest are bare (exomis: fastened on the left shoulder only, art-direction 5.4);
- skirt: `helper-skirt` from the belt to a hand above the knee (room to run);
- belt: a band of the tights at the waist, pushed out a little;
- sandals: a sole under each foot and three straps (ankle, instep, across the toes) from the skin.
Everything goes in one object `Tunic` with one material; the UV is split into regions of one 1024 texture (made by
melos_tex.py): undyed wool for the tunic (left 3/4), and in the right 1/4 the ochre belt, the straps and the soles.
The body under the tunic gets the vertex group `__under_tunic`, which lod_export.py deletes in the standard tier.

Frame: MPFB, metres, +Z up, the character faces -Y, his left is +X.
"""
import math

import bmesh
import bpy
from mathutils import Vector

HEM_Z = 0.60  # skirt hem, a hand above the knee (knee joint at z 0.51 for this build)
BELT_Z = (1.015, 1.045)  # belt band; the torso and the skirt both end inside it
NECK_Z = 1.47  # top of the left shoulder strap
ARM_X = 0.185  # armhole
# the diagonal from the left side of the neck down to under the right arm: above it on the right is bare skin
DIAG = ((0.06, NECK_Z), (-0.17, 1.25))
TORSO_PUSH = (0.006, 0.016)  # the wool stands off the skin: close at the shoulders, bloused above the belt
AXIS_Y = 0.005  # the body's vertical axis at the hips (pelvis joint y)
HEM_FLARE = 0.10  # the skirt widens towards the hem by this much (room for the thighs when running)
FRONT_EASE = 0.018  # extra cloth over the front of the thighs, around the hips (a lifted thigh stays inside)
BELT_PUSH = 0.022  # outside the bloused torso (TORSO_PUSH[1]) and the top of the skirt
STRAP_PUSH = 0.0025
# UV regions (u0, u1, v0, v1)
UV_WOOL = (0.0, 0.75, 0.0, 1.0)
UV_BELT = (0.75, 1.0, 0.0, 0.4)
UV_STRAPS = (0.75, 1.0, 0.4, 0.7)
UV_SOLES = (0.75, 1.0, 0.7, 1.0)


def _diag_plane():
    (x0, z0), (x1, z1) = DIAG
    d = Vector((x0 - x1, 0, z0 - z1)).normalized()
    n = Vector((-d.z, 0, d.x))  # points up and to his right: that side is cut away
    return Vector((x0, 0, z0)), n


def _copy_group(src, group, name):
    """A new mesh object made of the vertices of `src` whose weight in `group` is > 0.5 (shape keys dropped)."""
    me = src.data.copy()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = src.matrix_world.copy()
    if me.shape_keys:
        ob.shape_key_clear()
    gi = src.vertex_groups[group].index
    bm = bmesh.new()
    bm.from_mesh(me)
    dl = bm.verts.layers.deform.active
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not (gi in v[dl] and v[dl][gi] > 0.5)], context='VERTS')
    bm.to_mesh(me)
    bm.free()
    return ob


def _cut(ob, co, no):
    """Bisect `ob` with the plane (co, no) and delete the side `no` points to."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_outer=True, dist=1e-5)
    bm.to_mesh(ob.data)
    bm.free()


def _push(ob, dist, zmin=-1.0, zmax=9.0):
    ob.data.update()
    for v in ob.data.vertices:
        if zmin <= v.co.z <= zmax:
            v.co += v.normal * dist


def _push_graded(ob, dist, z_close, z_loose):
    """Push along the normals, dist[0] at z_close growing to dist[1] at z_loose."""
    ob.data.update()
    for v in ob.data.vertices:
        t = min(1.0, max(0.0, (z_close - v.co.z) / (z_close - z_loose)))
        v.co += v.normal * (dist[0] + (dist[1] - dist[0]) * t * t)


def _flare(ob, amount, z_top, z_hem):
    """Scale outwards from the body's vertical axis, 0 at z_top growing to `amount` at the hem."""
    for v in ob.data.vertices:
        t = min(1.0, max(0.0, (z_top - v.co.z) / (z_top - z_hem)))
        k = 1 + amount * t
        v.co.x *= k
        v.co.y = AXIS_Y + (v.co.y - AXIS_Y) * k


def _skirt_weights(ob, rig, z_top, z_hem, centre=0.06):
    """Reweight the skirt: the pelvis at the belt, the thighs towards the hem, blended smoothly across the middle
    (x within +-centre).  The helper skirt's own weights tear open at the front when one thigh lifts to run."""
    bones = [b.name for b in rig.data.bones]
    for name in ('pelvis', 'thigh_l', 'thigh_r'):
        if name not in ob.vertex_groups:
            ob.vertex_groups.new(name=name)
    idx = {g.name: g.index for g in ob.vertex_groups}
    for g in list(ob.vertex_groups):
        if g.name in bones:
            g.remove(range(len(ob.data.vertices)))
    for v in ob.data.vertices:
        t = min(1.0, max(0.0, (z_top - v.co.z) / (z_top - z_hem))) ** 0.5
        s = min(1.0, max(0.0, (v.co.x + centre) / (2 * centre)))
        s = s * s * (3 - 2 * s)  # smoothstep: his left thigh's share
        for name, w in (('pelvis', 1 - t), ('thigh_l', t * s), ('thigh_r', t * (1 - s))):
            if w > 1e-4:
                ob.vertex_groups[idx[name]].add([v.index], w, 'REPLACE')


def _front_ease(ob, dist, z_mid, half):
    """Push the front of the skirt out by up to `dist` around z_mid (+-half), fading to nothing at the sides."""
    ob.data.update()
    for v in ob.data.vertices:
        if v.co.y >= AXIS_Y:
            continue
        a = max(0.0, 1 - abs(v.co.z - z_mid) / half)
        f = min(1.0, (AXIS_Y - v.co.y) / 0.08)
        v.co += v.normal * dist * a * a * (3 - 2 * a) * f


def _keep_bone_groups(ob, rig):
    bones = {b.name for b in rig.data.bones}
    for g in list(ob.vertex_groups):
        if g.name not in bones:
            ob.vertex_groups.remove(g)


def _uv_into(ob, region, island_margin=0.02):
    """Smart-project `ob` and squeeze its UVs into `region` of the shared texture."""
    with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob],
                                   selected_editable_objects=[ob]):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=island_margin)
        bpy.ops.object.mode_set(mode='OBJECT')
    _squeeze(ob, region)


def _squeeze(ob, region):
    u0, u1, v0, v1 = region
    for d in ob.data.uv_layers.active.data:
        d.uv.x = u0 + d.uv.x * (u1 - u0)
        d.uv.y = v0 + d.uv.y * (v1 - v0)


def _join(objs, name):
    with bpy.context.temp_override(object=objs[0], active_object=objs[0], selected_objects=objs,
                                   selected_editable_objects=objs):
        bpy.ops.object.join()
    objs[0].name = name
    objs[0].data.name = name
    return objs[0]


def tunic_parts(body, rig):
    torso = _copy_group(body, 'helper-tights', 'tunic_torso')
    _cut(torso, Vector((0, 0, BELT_Z[0])), Vector((0, 0, -1)))
    _cut(torso, Vector((0, 0, NECK_Z)), Vector((0, 0, 1)))
    _cut(torso, Vector((ARM_X, 0, 0)), Vector((1, 0, 0)))
    _cut(torso, Vector((-ARM_X, 0, 0)), Vector((-1, 0, 0)))
    co, no = _diag_plane()
    _cut(torso, co, no)
    _push_graded(torso, TORSO_PUSH, NECK_Z, BELT_Z[1])

    skirt = _copy_group(body, 'helper-skirt', 'tunic_skirt')
    _cut(skirt, Vector((0, 0, HEM_Z)), Vector((0, 0, -1)))
    _cut(skirt, Vector((0, 0, BELT_Z[1])), Vector((0, 0, 1)))
    _flare(skirt, HEM_FLARE, BELT_Z[0], HEM_Z)
    _skirt_weights(skirt, rig, BELT_Z[0], HEM_Z)
    _front_ease(skirt, FRONT_EASE, 0.85, 0.12)

    belt = _copy_group(body, 'helper-tights', 'tunic_belt')
    _cut(belt, Vector((0, 0, BELT_Z[0] - 0.004)), Vector((0, 0, -1)))
    _cut(belt, Vector((0, 0, BELT_Z[1] + 0.004)), Vector((0, 0, 1)))
    _cut(belt, Vector((ARM_X, 0, 0)), Vector((1, 0, 0)))  # the hands hang at belt height in the A pose
    _cut(belt, Vector((-ARM_X, 0, 0)), Vector((-1, 0, 0)))
    _push(belt, BELT_PUSH)
    return torso, skirt, belt


def _hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def sandals(body, rig):
    """Soles from the outline of each foot, straps from bands of the skin.  Weighted to foot / ball bones."""
    me = bpy.data.meshes.new('sandals')
    bm = bmesh.new()
    mw = body.matrix_world
    skin = body.vertex_groups['body'].index
    feet = {'l': [], 'r': []}
    for v in body.data.vertices:
        if not any(g.group == skin and g.weight > 0.5 for g in v.groups):
            continue
        p = mw @ v.co
        if p.z < 0.10:
            feet['l' if p.x > 0 else 'r'].append((p, v))
    deform = bm.verts.layers.deform.verify()
    gi = {}

    def group(name):
        if name not in gi:
            gi[name] = len(gi)
        return gi[name]

    for side, vs in feet.items():
        # sole: hull of the bottom of the foot, 1 cm thick, the top face at 3 mm so the skin sits on it
        bottom = [(round(p.x, 4), round(p.y, 4)) for p, _ in vs if p.z < 0.018]
        ring = _hull(bottom)
        cx = sum(x for x, _ in ring) / len(ring)
        cy = sum(y for _, y in ring) / len(ring)
        grown = [(cx + (x - cx) * 1.06, cy + (y - cy) * 1.04) for x, y in ring]
        top = [bm.verts.new((x, y, 0.003)) for x, y in grown]
        bot = [bm.verts.new((x, y, -0.007)) for x, y in grown]
        bm.faces.new(top)
        bm.faces.new(list(reversed(bot)))
        for i in range(len(top)):
            j = (i + 1) % len(top)
            bm.faces.new((bot[i], bot[j], top[j], top[i]))
        for v in top + bot:
            # heel half on the foot bone, toe half on the ball bone
            v[deform][group(('ball_' if v.co.y < cy - 0.04 else 'foot_') + side)] = 1.0
    # planar UVs from above, each sole filling the soles region (both share the same leather)
    uvl = bm.loops.layers.uv.new('UVMap')  # same name as the body's, so join() merges them
    for f in bm.faces:
        side = 'l' if f.calc_center_median().x > 0 else 'r'
        ring = [v.co for v in bm.verts if (v.co.x > 0) == (side == 'l')]
        x0, x1 = min(c.x for c in ring), max(c.x for c in ring)
        y0, y1 = min(c.y for c in ring), max(c.y for c in ring)
        for lp in f.loops:
            lp[uvl].uv = ((lp.vert.co.x - x0) / (x1 - x0), (lp.vert.co.y - y0) / (y1 - y0))
    bm.to_mesh(me)
    bm.free()
    soles = bpy.data.objects.new('sandal_soles', me)
    bpy.context.scene.collection.objects.link(soles)
    for name in sorted(gi, key=gi.get):  # object group i = deform layer index i
        soles.vertex_groups.new(name=name)

    straps = _copy_group(body, 'body', 'sandal_straps')
    sm = straps.data
    bm = bmesh.new()
    bm.from_mesh(sm)
    keep = set()
    for v in bm.verts:
        p = mw @ v.co
        ax = 0.198 if p.x > 0 else -0.198  # ankle joint x
        if abs(abs(p.x) - abs(ax)) > 0.07 or p.z > 0.12:
            continue
        ankle = 0.072 <= p.z <= 0.088
        instep = abs(p.x - ax) < 0.007 and -0.15 < p.y < -0.02 and p.z > 0.025
        toes = -0.175 < p.y < -0.16 and p.z > 0.012
        if ankle or instep or toes:
            keep.add(v)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v not in keep], context='VERTS')
    bm.to_mesh(sm)
    bm.free()
    _push(straps, STRAP_PUSH)
    return soles, straps


def under_tunic(body):
    """Skin the tunic hides above the hips, with a margin of 3 cm: deleted from the standard tier (lod_export.py).
    The hips and thighs stay: the skirt lifts with the legs when he runs."""
    g = body.vertex_groups.get('__under_tunic') or body.vertex_groups.new(name='__under_tunic')
    co, no = _diag_plane()
    m = 0.03
    ids = []
    for v in body.data.vertices:
        p = v.co
        if not (0.92 < p.z < NECK_Z - m):
            continue
        if abs(p.x) > ARM_X - m:
            continue  # arms, and the hands hanging at hip height
        if p.z > BELT_Z[1] and (p - co).dot(no) > -m:
            continue  # the bare right shoulder
        ids.append(v.index)
    g.add(ids, 1.0, 'REPLACE')
    return len(ids)


def build(body_name='Human', rig_name='Human.rig'):
    body = bpy.data.objects[body_name]
    rig = bpy.data.objects[rig_name]
    torso, skirt, belt = tunic_parts(body, rig)
    soles, straps = sandals(body, rig)
    wool = _join([torso, skirt], 'tunic_wool')
    _uv_into(wool, UV_WOOL)
    _uv_into(belt, UV_BELT)
    _uv_into(straps, UV_STRAPS)
    _squeeze(soles, UV_SOLES)
    tunic = _join([wool, belt, straps, soles], 'Tunic')
    _keep_bone_groups(tunic, rig)
    # the parts were copied from the body: drop its skin material, one clothes material for everything
    tunic.data.materials.clear()
    mat = bpy.data.materials.get('M_tunic') or bpy.data.materials.new('M_tunic')
    tunic.data.materials.append(mat)
    for p in tunic.data.polygons:
        p.material_index = 0
    tunic.parent = rig
    tunic.matrix_parent_inverse = rig.matrix_world.inverted()
    m = tunic.modifiers.new('Armature', 'ARMATURE')
    m.object = rig
    n = under_tunic(body)
    return {'tunic_tris': sum(len(p.vertices) - 2 for p in tunic.data.polygons), 'under_tunic_verts': n}
