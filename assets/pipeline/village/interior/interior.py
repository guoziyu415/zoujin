# Inside Melos's house (F-11 range 1 and 6, ux/scenes/village.md 3): the sub-pack village-interior. The faces seen from
# inside (walls, the underside of the roof, the earth floor, the reveals of the door and the two shuttered windows) and
# the things in the room: the hearth, the bench along the south wall, the loom and the amphorae at the west end,
# Melos's straw mat, the low feast tables. The outside of the walls and the roof are the village pack's.
# Two lights, baked onto one lightmap layout:
#   day   - the sky through the north door and windows (11:00, the sun on the yard outside throws its bounce in; the
#           sun itself never reaches the floor from 10:30 to 16:00); indirect only, the page's live sun adds the low
#           evening slant through the door.
#   feast - the second night: the hearth and four oil lamps, the door open on a rainy night (a cold, dim sky).
# Plan frame as the village (village.md 2): +x east, +y north, z up from the yard; no rotation (SCENE_MINUS_X_AZ 270).
# Writes into PLAZA_OUT: interior_raw.glb (the exported room, both UV layers), lm_<set>.png (baked / K, sRGB, rows
# top-down), lm_meta.json (K per set, the lightmap size, the floor's light at a few points for the people's light).
#   BPY_PYTHON interior.py -- final|draft
import bpy, bmesh, math, os, sys, json   # bpy first: it brings mathutils
import numpy as np
from mathutils import Vector, Matrix, geometry
from mathutils.bvhtree import BVHTree
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'common'))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'plaza'))
import bl
from bl import box, cyl, coll, obj_from_bm, box_uv_bm
from sunpos import sun_local

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
Q = argv[0] if argv else 'final'
OUT = os.environ['PLAZA_OUT']
scene = bl.setup(f'{OUT}/tex')
mat, pbr, tex_exists = bl.mat, bl.pbr, bl.tex_exists

# ---------------------------------------------------------------- the room: inside the walls of ../build_village.py
# house('melos', ...): wall centre lines x -14..-2, y -14..-8.5, 0.5 m thick; the lean-to roof's underside from 3.0 m
# over the north (door) wall to 4.21 m over the south; the door 1.1 x 2.1 m at x -8, two windows 0.7 m wide, 1.2 to
# 1.9 m. The village pack has the walls' own inner faces and the roof's underside, lit by the outdoor bake: these faces
# stand INSET in front of them (and the floor INSET above the yard's ground) so that only these are seen inside.
CX0, CX1, CY0, CY1, T = -14.0, -2.0, -14.0, -8.5, 0.5
INSET = 0.02
X0, X1, Y0, Y1 = CX0 - T / 2, CX1 + T / 2, CY0 - T / 2, CY1 + T / 2          # the walls' outside
IX0, IX1, IY0, IY1 = CX0 + T / 2 + INSET, CX1 - T / 2 - INSET, CY0 + T / 2 + INSET, CY1 - T / 2 - INSET
EAVE, HI = 3.0, 3.0 + (CY1 - CY0) * 0.22


def roof_z(y):
    """the underside of the room's ceiling at plan y (the village roof's underside, INSET lower)"""
    return HI + (EAVE - HI) * (y - CY0) / (CY1 - CY0) - INSET


H_N, H_S = roof_z(IY1), roof_z(IY0)
DOOR = (-8.55 + INSET, -7.45 - INSET, 2.1 - INSET)   # x0, x1, head height: the reveals inset into the opening
WINDOWS = [(-11.85 + INSET, -11.15 - INSET), (-4.85 + INSET, -4.15 - INSET)]   # x spans in the north wall
SILL, HEAD = 1.2 + INSET, 1.9 - INSET
HEARTH = (-8.0, -11.5)


# ---------------------------------------------------------------- materials (texture keys: ../../plaza/placeholder_tex.py)
M_FLOOR = mat('earthfloor', tex_exists('plain_base'), tex_exists('plain_nrm'), tex_exists('plain_mr'))
M_PLASTER = mat('plaster', tex_exists('plaster_base'), tex_exists('plain_nrm'), None, rough=0.9)
M_WOOD = mat('wood', tex_exists('doors_base'), tex_exists('doors_nrm'), tex_exists('doors_mr'))
M_STONE = pbr('ashlar', 'ashlar')
M_CLAY = mat('terracotta', None, None, None, color=(0.55, 0.27, 0.15), rough=0.8)
M_STRAW = mat('straw', None, None, None, color=(0.62, 0.52, 0.30), rough=0.95)
M_ASH = mat('ash', None, None, None, color=(0.16, 0.15, 0.14), rough=1.0)
M_WOOL = mat('wool', None, None, None, color=(0.70, 0.64, 0.52), rough=0.95)
M_BREAD = mat('bread', None, None, None, color=(0.60, 0.40, 0.20), rough=0.9)
# not exported: the house's outside and the yard (they shade and bounce the bake), and the fire's glow
M_OUT = mat('outside', None, None, None, color=(0.55, 0.50, 0.42), rough=0.9)
M_FIRE = bpy.data.materials.new('fire'); M_FIRE.use_nodes = True
_fn = M_FIRE.node_tree.nodes
_fn['Principled BSDF'].inputs['Base Color'].default_value = (0, 0, 0, 1)
_fn['Principled BSDF'].inputs['Emission Color'].default_value = (1.0, 0.42, 0.12, 1)
_fn['Principled BSDF'].inputs['Emission Strength'].default_value = 0.0   # lit for the feast bake only


def quad_faces(name, quads, m, group='room', tile=2.0, facing=None):
    """faces from lists of corner points; facing (x, y, z) turns each to face that way (else its winding decides)"""
    bm = bmesh.new()
    for q in quads:
        f = bm.faces.new([bm.verts.new(p) for p in q])
        f.normal_update()
        if facing is not None and f.normal.dot(Vector(facing)) < 0:
            f.normal_flip()
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.normal_update()
    box_uv_bm(bm, tile)
    return obj_from_bm(name, bm, [m], group)


def wall_cells(us, zs, holes):
    """grid cells (u0, u1, z0, z1) of a wall on the lines us x zs, without the ones inside a hole (u0, u1, z0, z1)"""
    out = []
    for a, b in zip(us, us[1:]):
        for c, d in zip(zs, zs[1:]):
            mu, mz = (a + b) / 2, (c + d) / 2
            if any(h[0] < mu < h[1] and h[2] < mz < h[3] for h in holes):
                continue
            out.append((a, b, c, d))
    return out


# ---------------------------------------------------------------- walls, seen from inside
holes = [(DOOR[0], DOOR[1], INSET, DOOR[2])] + [(w0, w1, SILL, HEAD) for w0, w1 in WINDOWS]
us = sorted({IX0, IX1, DOOR[0], DOOR[1]} | {u for w in WINDOWS for u in w})
zs = [INSET, SILL, HEAD, DOOR[2], H_N]
north = [[(a, IY1, c), (a, IY1, d), (b, IY1, d), (b, IY1, c)] for a, b, c, d in wall_cells(us, zs, holes)]
south = [[(IX0, IY0, INSET), (IX1, IY0, INSET), (IX1, IY0, H_S), (IX0, IY0, H_S)]]
west = [[(IX0, IY1, INSET), (IX0, IY0, INSET), (IX0, IY0, H_S), (IX0, IY1, H_N)]]
east = [[(IX1, IY0, INSET), (IX1, IY1, INSET), (IX1, IY1, H_N), (IX1, IY0, H_S)]]
quad_faces('wall_n', north, M_PLASTER, facing=(0, -1, 0))
quad_faces('wall_s', south, M_PLASTER, facing=(0, 1, 0))
quad_faces('wall_w', west, M_PLASTER, facing=(1, 0, 0))
quad_faces('wall_e', east, M_PLASTER, facing=(-1, 0, 0))
for k, (x0, x1, z0, z1) in enumerate(holes):   # the reveals face into the opening
    yi, yo = IY1, Y1
    quad_faces(f'jamb{k}w', [[(x0, yi, z0), (x0, yo, z0), (x0, yo, z1), (x0, yi, z1)]], M_PLASTER, facing=(1, 0, 0))
    quad_faces(f'jamb{k}e', [[(x1, yi, z0), (x1, yo, z0), (x1, yo, z1), (x1, yi, z1)]], M_PLASTER, facing=(-1, 0, 0))
    quad_faces(f'head{k}', [[(x0, yi, z1), (x0, yo, z1), (x1, yo, z1), (x1, yi, z1)]], M_PLASTER, facing=(0, 0, -1))
    if z0 > INSET:
        quad_faces(f'sill{k}', [[(x0, yi, z0), (x0, yo, z0), (x1, yo, z0), (x1, yi, z0)]], M_PLASTER, facing=(0, 0, 1))
quad_faces('ceiling', [[(IX0, IY1, H_N), (IX1, IY1, H_N), (IX1, IY0, H_S), (IX0, IY0, H_S)]], M_WOOD,
           facing=(0, 0, -1))
quad_faces('floor', [[(IX0, IY0, INSET), (IX0, IY1, INSET), (IX1, IY1, INSET), (IX1, IY0, INSET)]], M_FLOOR, tile=3.0,
           facing=(0, 0, 1))
# the door's threshold stone, so the doorway is not a hole in the floor
quad_faces('threshold', [[(DOOR[0], IY1, INSET), (DOOR[0], Y1, INSET), (DOOR[1], Y1, INSET), (DOOR[1], IY1, INSET)]],
           M_STONE, facing=(0, 0, 1))

# ---------------------------------------------------------------- the roof's timbers: a beam along the room under the
# middle, and rafters from the north wall to the south wall
for i in range(7):
    x = IX0 + 0.5 + i * (IX1 - IX0 - 1.0) / 6
    zn, zs_ = H_N - 0.14, H_S - 0.14
    rafter = bl.rod(f'rafter{i}', Vector((x, IY1, zn + 0.07)), Vector((x, IY0, zs_ + 0.07)), 0.07, M_WOOD, group='room')
ym = (IY0 + IY1) / 2
bl.rod('beam', Vector((IX0, ym, roof_z(ym) - 0.28)), Vector((IX1, ym, roof_z(ym) - 0.28)), 0.11, M_WOOD, group='room')
for x in (-11.0, -5.0):
    bl.rod(f'post{x}', Vector((x, ym, 0)), Vector((x, ym, roof_z(ym) - 0.28)), 0.09, M_WOOD, group='room')

# ---------------------------------------------------------------- the hearth: a ring of stones round the ash, a few
# logs (cold by day; the feast lights the glow over them)
hx, hy = HEARTH
for k in range(11):
    a = 2 * math.pi * k / 11
    r = 0.58
    box(f'hstone{k}', -0.13, 0.13, -0.09, 0.09, 0.0, 0.14 + 0.03 * (k % 3), M_STONE, group='room', tile=0.8,
        xform=Matrix.Translation((hx + r * math.cos(a), hy + r * math.sin(a), 0)) @ Matrix.Rotation(a, 4, 'Z'))
cyl('ash', hx, hy, 0.0, 0.05, 0.48, seg=14, m=M_ASH, group='room')
for k, (a, z) in enumerate([(0.3, 0.06), (1.9, 0.08), (3.6, 0.07)]):
    c, s = math.cos(a), math.sin(a)
    bl.rod(f'log{k}', Vector((hx - 0.32 * c, hy - 0.32 * s, z)), Vector((hx + 0.3 * c, hy + 0.3 * s, z + 0.05)), 0.05,
           M_WOOD, group='room')
glow = cyl('glow', hx, hy, 0.04, 0.34, 0.26, 0.05, seg=10, m=M_FIRE, group='light')

# ---------------------------------------------------------------- the bench along the south wall
box('bench', IX0 + 1.0, IX1 - 1.0, IY0, IY0 + 0.42, 0.40, 0.47, M_WOOD, group='room', tile=1.5, caster=True)
for x in [IX0 + 1.1 + i * (IX1 - IX0 - 2.2) / 5 for i in range(6)]:
    box(f'benchleg{x:.1f}', x - 0.05, x + 0.05, IY0 + 0.05, IY0 + 0.37, 0.0, 0.40, M_WOOD, group='room', tile=1.0)

# ---------------------------------------------------------------- the loom against the west wall: two posts leaning on
# the wall, a beam across the top with the cloth begun, the warp hanging to the weights
lx = IX0 + 0.25
for y in (-10.55, -9.45):
    bl.rod(f'loompost{y}', Vector((lx + 0.35, y, 0)), Vector((lx, y, 2.05)), 0.045, M_WOOD, group='room')
bl.rod('loombeam', Vector((lx + 0.02, -10.65, 1.95)), Vector((lx + 0.02, -9.35, 1.95)), 0.05, M_WOOD, group='room')
bl.rod('loomrod', Vector((lx + 0.2, -10.6, 0.95)), Vector((lx + 0.2, -9.4, 0.95)), 0.025, M_WOOD, group='room')
quad_faces('warp', [[(lx + 0.03, -10.45, 1.9), (lx + 0.03, -9.55, 1.9), (lx + 0.22, -9.55, 0.6),
                     (lx + 0.22, -10.45, 0.6)],
                    [(lx + 0.22, -10.45, 0.6), (lx + 0.22, -9.55, 0.6), (lx + 0.03, -9.55, 1.9),
                     (lx + 0.03, -10.45, 1.9)]], M_WOOL, tile=1.0)
for k in range(8):
    y = -10.4 + k * 0.8 / 7
    box(f'weight{k}', lx + 0.18, lx + 0.28, y - 0.04, y + 0.04, 0.42, 0.58, M_CLAY, group='room', tile=0.5)


# ---------------------------------------------------------------- amphorae in the south-west corner
def amphora(name, x, y, h=0.72, lean=0.0):
    prof = [(0.0, 0.0), (0.05, 0.02), (0.16, 0.18), (0.20, 0.36), (0.17, 0.52), (0.08, 0.62), (0.06, 0.70),
            (0.08, h)]
    bm = bmesh.new()
    seg = 12
    rings = []
    for r, z in prof:
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), z))
                      for i in range(seg)])
    for a, b in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.transform(bm, matrix=Matrix.Translation((x, y, 0)) @ Matrix.Rotation(lean, 4, 'X'), verts=bm.verts)
    bm.normal_update()
    box_uv_bm(bm, 0.6)
    return obj_from_bm(name, bm, [M_CLAY], 'room', caster=True)


for k, (x, y, lean) in enumerate([(IX0 + 0.3, IY0 + 0.3, 0.0), (IX0 + 0.75, IY0 + 0.25, 0.05),
                                  (IX0 + 0.3, IY0 + 0.78, -0.04), (IX0 + 1.2, IY0 + 0.3, 0.0)]):
    amphora(f'amphora{k}', x, y, 0.72 - 0.06 * (k % 2), lean)

# ---------------------------------------------------------------- Melos's straw mat (melos-sleep, (-11, -12.5))
box('mat', -11.95, -10.05, -12.95, -12.1, 0.0, 0.07, M_STRAW, group='room', tile=1.0,
    xform=Matrix.Translation((-11, -12.5, 0)) @ Matrix.Rotation(0.06, 4, 'Z') @ Matrix.Translation((11, 12.5, 0)))
box('fleece', -11.7, -11.0, -12.85, -12.2, 0.07, 0.11, M_WOOL, group='room', tile=0.8)

# ---------------------------------------------------------------- the feast: low tables in the east half (laid on the
# first day already, "祝宴の席を調え"), the head table before the bride and groom at the east end
TABLES = [(-6.7, -4.9, -12.45, -11.85), (-6.7, -4.9, -10.15, -9.55), (-4.6, -4.05, -12.6, -9.9)]
for k, (x0, x1, y0, y1) in enumerate(TABLES):
    box(f'table{k}', x0, x1, y0, y1, 0.36, 0.42, M_WOOD, group='room', tile=1.2, caster=True)
    for (x, y) in [(x0 + 0.08, y0 + 0.08), (x1 - 0.08, y0 + 0.08), (x0 + 0.08, y1 - 0.08), (x1 - 0.08, y1 - 0.08)]:
        box(f'tleg{k}_{x:.2f}_{y:.2f}', x - 0.04, x + 0.04, y - 0.04, y + 0.04, 0.0, 0.36, M_WOOD, group='room', tile=0.5)
    n = 4 if k < 2 else 3
    for i in range(n):
        if k < 2:
            x, y = x0 + 0.25 + i * (x1 - x0 - 0.5) / (n - 1), (y0 + y1) / 2 + (0.12 if i % 2 else -0.12)
        else:
            x, y = (x0 + x1) / 2 + (0.08 if i % 2 else -0.08), y0 + 0.4 + i * (y1 - y0 - 0.8) / (n - 1)
        cyl(f'cup{k}_{i}', x, y, 0.42, 0.50, 0.04, 0.05, seg=8, m=M_CLAY, group='room')
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=5, radius=0.09)
        bmesh.ops.transform(bm, matrix=Matrix.Translation((x + 0.14, y, 0.44)) @ Matrix.Diagonal((1, 1, 0.45, 1)),
                            verts=bm.verts)
        bm.normal_update(); box_uv_bm(bm, 0.5)
        obj_from_bm(f'bread{k}_{i}', bm, [M_BREAD], 'room')

# ---------------------------------------------------------------- oil lamps: a shelf by the door, one on each table
LAMPS = [(-9.6, IY1 - 0.12, 1.55), (-5.8, -12.15, 0.48), (-5.8, -9.85, 0.48), (-4.32, -11.25, 0.48)]
for k, (x, y, z) in enumerate(LAMPS):
    if k == 0:
        box('shelf', x - 0.25, x + 0.25, IY1 - 0.22, IY1, z - 0.06, z - 0.02, M_WOOD, group='room', tile=0.6)
    cyl(f'lamp{k}', x, y, z - 0.02, z + 0.03, 0.05, 0.035, seg=8, m=M_CLAY, group='room')

# ---------------------------------------------------------------- outside (the bake only): the house's shell with the
# openings, its roof, the yard and the yard wall north of the door
o = 'occ'
shell = []
for a, b, c, d in wall_cells(us, zs, holes):
    shell.append([(b, Y1, c), (b, Y1, d), (a, Y1, d), (a, Y1, c)])
zr = lambda y: HI + (EAVE - HI) * (y - CY0) / (CY1 - CY0)
shell += [[(X1, Y0, 0), (X0, Y0, 0), (X0, Y0, zr(Y0)), (X1, Y0, zr(Y0))],
          [(X0, Y0, 0), (X0, Y1, 0), (X0, Y1, zr(Y1)), (X0, Y0, zr(Y0))],
          [(X1, Y1, 0), (X1, Y0, 0), (X1, Y0, zr(Y0)), (X1, Y1, zr(Y1))],
          [(CX0 - 0.45, CY0 - 0.45, zr(CY0 - 0.45)), (CX1 + 0.45, CY0 - 0.45, zr(CY0 - 0.45)),
           (CX1 + 0.45, CY1 + 0.45, zr(CY1 + 0.45)), (CX0 - 0.45, CY1 + 0.45, zr(CY1 + 0.45))]]
quad_faces('shell', shell, M_OUT, group=o)
quad_faces('yard', [[(-40, Y1, 0), (30, Y1, 0), (30, 30, 0), (-40, 30, 0)],
                    [(-40, -40, -0.01), (30, -40, -0.01), (30, Y1, -0.01), (-40, Y1, -0.01)]], M_OUT, group=o, tile=4,
          facing=(0, 0, 1))
box('yardwall', -14.0, 2.0, -0.95, -0.5, 0.0, 1.8, M_OUT, group=o)   # village.md 2.1: the yard wall's north side
box('doorleaf', -8.55, -8.47, -8.2, -7.2, 0.0, 2.08, M_OUT, group=o)   # build_village.py: open out into the yard

# ---------------------------------------------------------------- one object for the room, one lightmap layout
vl = bpy.context.view_layer


def select_only(objs):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objs:
        ob.select_set(True)
    vl.objects.active = objs[0]


room_objs = [ob for ob in coll('room').objects if ob.type == 'MESH']
casters = [ob for ob in room_objs if ob.get('caster') == 1]
select_only(room_objs)
bpy.ops.object.join()
room = vl.objects.active
room.name = room.data.name = 'interior'
me = room.data
lm = me.uv_layers.new(name='lightmap')
me.uv_layers.active = lm
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0, area_weight=0.0, correct_aspect=True,
                         scale_to_bounds=False)
bpy.ops.uv.pack_islands(margin=0.006, rotate=True, shape_method='CONCAVE')
bpy.ops.object.mode_set(mode='OBJECT')
me.uv_layers['UVMap'].active_render = True

# ---------------------------------------------------------------- light and bake
RES = 512 if Q == 'final' else 128
SPP = {'day_full': 128, 'day_direct': 16, 'feast': 192} if Q == 'final' else {'day_full': 16, 'day_direct': 4,
                                                                              'feast': 16}
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.max_bounces = 6
scene.cycles.seed = 7
world = bpy.data.worlds.new('World'); scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes['Background']
# the day: ../../plaza/sky.py's sky for 11:00 (build.sh runs it first), as the outdoor bakes; the feast: a flat
# cold, dim rainy night
env = world.node_tree.nodes.new('ShaderNodeTexEnvironment')
env.image = bpy.data.images.load(f'{OUT}/sky_sunset.hdr')
WL = world.node_tree.links
SUN_LOCAL, SUN_EL, SUN_AZ = sun_local(660)   # 11:00 (village.md 3: Melos sleeps from 10:30)
ld = bpy.data.lights.new('Sun', 'SUN'); ld.angle = math.radians(1.2)
sun = bpy.data.objects.new('Sun', ld); scene.collection.objects.link(sun)
sun.rotation_euler = (-SUN_LOCAL).to_track_quat('-Z', 'Y').to_euler()
fire_lights = []
for k, (pos, watts, size) in enumerate([((hx, hy, 0.35), 260.0, 0.25)] + [((x, y, z + 0.08), 14.0, 0.03)
                                                                       for x, y, z in LAMPS]):
    pl = bpy.data.lights.new(f'fire{k}', 'POINT')
    pl.color = (1.0, 0.50, 0.20); pl.shadow_soft_size = size
    ob = bpy.data.objects.new(f'fire{k}', pl); ob.location = pos; scene.collection.objects.link(ob)
    fire_lights.append(pl)


def light_set(name):
    if name.startswith('day'):
        WL.new(env.outputs['Color'], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = 1.0 if name == 'day_full' else 0.0
        ld.energy = 6.0; ld.color = (1.0, 0.94, 0.87)                # sun.ts at 68°, 5500 K
        _fn['Principled BSDF'].inputs['Emission Strength'].default_value = 0.0
        for pl, w in zip(fire_lights, [0] * len(fire_lights)):
            pl.energy = w
    else:
        for lk in list(bg.inputs['Color'].links):
            WL.remove(lk)
        bg.inputs['Color'].default_value = (0.16, 0.20, 0.27, 1)   # rain at night: cold and very dim
        bg.inputs['Strength'].default_value = 0.035
        ld.energy = 0.0
        _fn['Principled BSDF'].inputs['Emission Strength'].default_value = 6.0
        for pl, w in zip(fire_lights, [260.0] + [14.0] * len(LAMPS)):
            pl.energy = w


def bake(name):
    light_set(name)
    im = bpy.data.images.new(f'lm_{name}', RES, RES, float_buffer=True)
    for m in me.materials:
        nt = m.node_tree
        n = nt.nodes.get('__bake__') or nt.nodes.new('ShaderNodeTexImage')
        n.name = '__bake__'; n.image = im
        for x in nt.nodes:
            x.select = False
        n.select = True; nt.nodes.active = n
    select_only([room])
    scene.cycles.samples = SPP[name]
    direct = name == 'day_direct'
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'DIRECT'} if direct else {'DIRECT', 'INDIRECT'},
                        uv_layer='lightmap', use_clear=True, margin=8)
    a = np.array(im.pixels[:], dtype=np.float32).reshape(RES, RES, 4)[..., :3]
    print('baked', name, RES, SPP[name], 'spp', flush=True)
    return a


bakes = {k: bake(k) for k in ('day_full', 'day_direct', 'feast')}
sets = {'day': np.clip(bakes['day_full'] - bakes['day_direct'], 0, None), 'feast': bakes['feast']}
for m in me.materials:
    if '__bake__' in m.node_tree.nodes:
        m.node_tree.nodes.remove(m.node_tree.nodes['__bake__'])

# ---------------------------------------------------------------- encode (as ../../plaza/encode.py: baked / K, sRGB)
from PIL import Image, ImageFilter
LUM = np.array([0.2126, 0.7152, 0.0722])
meta = {'res': RES, 'sets': {}, 'sunAtDay': [round(SUN_EL, 2), round(SUN_AZ, 1)], 'room': [IX0, IY0, IX1, IY1, H_S],
        # the feast's flames for the page: plan (x, y), height, size in metres
        'flames': [[hx, hy, 0.12, 0.5]] + [[x, y, z + 0.04, 0.07] for x, y, z in LAMPS]}
# the floor's light at a few points (the people's light in the room: the page lights them from these, F-11 range 5)
PROBES = {'door': (-8.0, -9.4), 'middle': (-8.0, -10.6), 'west': (-11.5, -11.4), 'east': (-4.6, -11.2),
          'loom': (-12.6, -10.0)}
bvh_mesh = room.data
bvh = BVHTree.FromObject(room, bpy.context.evaluated_depsgraph_get())
lmd = bvh_mesh.uv_layers['lightmap'].data


bvh_mesh.calc_loop_triangles()


def floor_uv(x, y):
    """the lightmap UV of the floor (or whatever lies on it) under plan (x, y)"""
    loc, _, fi, _ = bvh.ray_cast(Vector((x, y, 0.3)), Vector((0, 0, -1)))
    for tri in bvh_mesh.loop_triangles:
        if tri.polygon_index != fi:
            continue
        p = [bvh_mesh.vertices[v].co for v in tri.vertices]
        uv = [lmd[li].uv.to_3d() for li in tri.loops]
        if geometry.intersect_point_tri_2d(loc.xy, p[0].xy, p[1].xy, p[2].xy):
            return geometry.barycentric_transform(loc, *p, *uv).xy
    raise RuntimeError(f'no floor under ({x}, {y})')


for name, a in sets.items():
    lum = a @ LUM
    K = float(np.percentile(lum[lum > 1e-5], 99.7)) * 1.15
    s = np.clip(a / K, 0, 1)
    s = np.where(s <= 0.0031308, s * 12.92, 1.055 * np.power(s, 1 / 2.4) - 0.055)
    Image.fromarray((s * 255 + 0.5).astype(np.uint8)[::-1], 'RGB').filter(ImageFilter.GaussianBlur(0.6)).save(
        f'{OUT}/lm_{name}.png', optimize=True)
    probes = {}
    for pid, (x, y) in PROBES.items():
        u, v = floor_uv(x, y)
        px, py = min(RES - 1, int(u * RES)), min(RES - 1, int(v * RES))
        probes[pid] = {'at': [x, y], 'rgb': [round(float(c), 4) for c in a[py, px]]}
    meta['sets'][name] = {'K': round(K, 5), 'floor': probes}
    print(name, 'K', round(K, 4), {k: v['rgb'] for k, v in probes.items()})
json.dump(meta, open(f'{OUT}/lm_meta.json', 'w'), indent=1, sort_keys=True)

# ---------------------------------------------------------------- export the room (glTF, +Y up)
for ob in list(scene.objects):
    ob.select_set(False)
room.select_set(True); vl.objects.active = room
bpy.ops.export_scene.gltf(filepath=f'{OUT}/interior_raw.glb', export_format='GLB', use_selection=True,
                          export_texcoords=True, export_normals=True, export_materials='EXPORT',
                          export_image_format='AUTO', export_apply=True, export_yup=True, export_extras=False)
print('exported', len(me.polygons), 'faces')
