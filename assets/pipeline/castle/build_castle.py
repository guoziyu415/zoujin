# The castle (F-14, ux/scenes/castle.md v1.0.2): gate passage, courtyard with four porticoes, throne hall, tower.
# Plan frame (castle.md 2): +x = east (azimuth 90°, into the castle), +y = north, z = 0 on the courtyard floor.
# No rotation (layout rotationDeg 0), so the sun scripts get SCENE_MINUS_X_AZ = 270.
# The bake is the night of the promise (20:30): the lamps and braziers of layout.json `lamps` are Blender point lights,
# the sky is a moonless one, there is no sun. By day the page lights the courtyard with the live sun over the baked
# occlusion, as the plaza; inside the hall it keeps the lamps by day too (castle.md 3, PM A).
import bpy, os, sys, math, json   # bpy first: it brings mathutils
import bmesh
from mathutils import Vector, Matrix, noise
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import bl
from bl import box, cyl, rod, heightfield, lines

OUT = os.environ['PLAZA_OUT']
STEM = os.environ['SCENE_STEM']
LAYOUT = json.load(open(os.environ['CASTLE_LAYOUT'], encoding='utf-8'))
bl.setup(f'{OUT}/tex')
mat, pbr, tex_exists = bl.mat, bl.pbr, bl.tex_exists

# ---------------------------------------------------------------- materials (texture keys: castle_tex.py)
M_FLAGS = pbr('floor', 'floor')           # named floor: the page's ambient ground colour reads materials.floor
M_HALL = pbr('hallfloor', 'hallfloor')
M_AXIS = mat('hallaxis', tex_exists('hallaxis_base'), tex_exists('hallfloor_nrm'), tex_exists('hallfloor_mr'))
M_ASHLAR = pbr('ashlar', 'ashlar')
M_PLASTER = mat('plaster', tex_exists('plaster_base'), tex_exists('plain_nrm'), tex_exists('plain_mr'))
M_DADO = mat('dado', tex_exists('dado_base'), tex_exists('plain_nrm'), None, rough=0.8)
M_ROOF = mat('roofwarm', tex_exists('roofwarm_base'), None, None, rough=0.8)
M_WOOD = mat('beam', tex_exists('throne_base'), None, None, rough=0.75)
M_SHUTTER = mat('shutter', tex_exists('throne_base'), tex_exists('throne_nrm'), None, rough=0.8)
M_CURTAIN = pbr('curtain', 'curtain')
M_THRONE = pbr('throne', 'throne')
M_BRONZE = pbr('bronze', 'bronze')
M_EMBER = mat('embers', color=(0.12, 0.05, 0.03), rough=0.95)   # the page draws the flames over them
M_WELL = mat('wellmouth', color=(0.03, 0.035, 0.035), rough=0.3)
M_HILL = mat('hill', tex_exists('hill_base'), tex_exists('plain_nrm'), None, rough=0.95)
M_CYPRESS = mat('cypress', tex_exists('cypress_base'), None, None, rough=0.85)

HALL_X, HALL_Y, HALL_H = (-6.0, 16.0), 7.0, 8.0     # the hall's inside (castle.md 2); walls 0.8 thick outside it
WALL = 0.8
YARD_H = 8.0                                         # the courtyard's walls: the west one throws the 16:00 shadow


# ---------------------------------------------------------------- the ground
def ground_mat(cx, cy, cz):
    inside = HALL_X[0] - WALL <= cx <= HALL_X[1] + WALL and abs(cy) <= HALL_Y + WALL
    if inside and HALL_X[0] - WALL <= cx <= 10.0 and abs(cy) <= 1.0:
        return 2   # the paler stone band on the axis, door to steps (castle.md 3.1)
    return 1 if inside else 0

XS = lines((-34, 24, 1.0), extra=(HALL_X[0] - WALL, HALL_X[0], HALL_X[1], HALL_X[1] + WALL))
YS = lines((-12, 16, 1.0), extra=(-HALL_Y - WALL, -HALL_Y, HALL_Y, HALL_Y + WALL))
heightfield('ground', XS, YS, lambda x, y: 0.0, ground_mat, [M_FLAGS, M_HALL, M_AXIS], 'ground', tile=1.2)


# ---------------------------------------------------------------- far: the city below to the west, hills around
def far_height(x, y):
    d = math.hypot(x, y)
    h = -10.0 if x < -40 else -4.0                       # the castle stands on the high ground east of the square
    hills = 50 * (min(1.0, max(0.0, (d - 220) / 260)) ** 1.5)
    hills *= 1 + 0.4 * noise.noise(Vector((x / 160, y / 160, 0.7)))
    return h + hills

def far_skip(cx, cy):
    return -36 < cx < 26 and -14 < cy < 18

FX = lines((-600, 600, 30), extra=(-36, 26))
FY = lines((-600, 600, 30), extra=(-14, 18))
heightfield('far_land', FX, FY, far_height, lambda *a: 0, [M_HILL], 'far', skip=far_skip, tile=40.0)

def city():
    """flat roofs of the city stepping down to the square, west of the gate (seen through the gate passage)"""
    import random
    rr = random.Random(11)
    for i in range(26):
        x = -48 - rr.uniform(0, 70)
        y = rr.uniform(-60, 60)
        w, d, h = rr.uniform(5, 11), rr.uniform(5, 11), rr.uniform(4, 9)
        box(f'house{i}', x - w / 2, x + w / 2, y - d / 2, y + d / 2, -10.0, -10.0 + h, M_PLASTER, group='far')
    for i in range(10):
        x, y = -45 - rr.uniform(0, 60), rr.uniform(-50, 50)
        cyl(f'cypress{i}', x, y, -10.0, -10.0 + rr.uniform(9, 13), 1.0, 0.25, seg=8, m=M_CYPRESS, group='far')
city()


# ---------------------------------------------------------------- walls of the courtyard and the gatehouse
X0, X1 = -24.0, HALL_X[0] - WALL                       # the courtyard's inner faces west and east (x)
YC = 10.0                                              # and north / south (y)
for s in (1, -1):
    y0, y1 = sorted((s * YC, s * (YC + WALL)))
    box(f'yardwall{s}', X0 - WALL, X1, y0, y1, 0, YARD_H, M_ASHLAR, caster=True)
    # west wall either side of the gatehouse, east wall either side of the hall
    y0, y1 = sorted((s * 5.0, s * (YC + WALL)))
    box(f'westwall{s}', X0 - WALL, X0, y0, y1, 0, YARD_H, M_ASHLAR, caster=True)
    y0, y1 = sorted((s * (HALL_Y + WALL), s * (YC + WALL)))
    box(f'eastwall{s}', X1, HALL_X[0], y0, y1, 0, YARD_H, M_ASHLAR, caster=True)
    # the gatehouse: two blocks either side of the 4 m passage under one steep stone cap (10.6 m at the ridge)
    y0, y1 = sorted((s * 2.0, s * 5.0))
    box(f'gatehouse{s}', -30.0, X0, y0, y1, 0, 7.2, M_ASHLAR, caster=True)
def lintel(name, x0, x1, y0, y1, z0, z1, m):
    """the stone over the passage: its two faces and its soffit, no top (the cap closes it): a flat top over a walkable
    passage becomes a floor of its own for the navmesh, and nav.mjs takes the first polygon over the start spot"""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z)) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    for q in ((0, 2, 3, 1), (0, 1, 5, 4), (2, 6, 7, 3)):
        bm.faces.new([vs[i] for i in q])
    bm.normal_update(); bl.box_uv_bm(bm, 4.0)
    return bl.obj_from_bm(name, bm, [m], 'arch', caster=True)

lintel('gatelintel', -30.0, X0, -2.0, 2.0, 5.0, 7.2, M_ASHLAR)

def ridge_cap(name, x0, x1, y0, y1, z, rise, m):
    """a stone cap with its ridge along y, slopes too steep to walk (no floor on top of the passage either)"""
    xm = (x0 + x1) / 2
    bm = bmesh.new()
    a, b, c, d = [bm.verts.new(v) for v in ((x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z))]
    r0, r1 = bm.verts.new((xm, y0, z + rise)), bm.verts.new((xm, y1, z + rise))
    bm.faces.new((b, c, r1, r0)); bm.faces.new((d, a, r0, r1))
    bm.faces.new((a, b, r0)); bm.faces.new((c, d, r1))
    bm.normal_update(); bl.box_uv_bm(bm, 2.0)
    return bl.obj_from_bm(name, bm, [m], 'arch', caster=True)

ridge_cap('gatecap', -30.0, X0, -5.0, 5.0, 7.2, 3.4, M_ASHLAR)
box('apronwall_n', -34.0, -30.0, 2.0, 2.5, 0, 1.0, M_ASHLAR)   # low parapets along the apron's edges
box('apronwall_s', -34.0, -30.0, -2.5, -2.0, 0, 1.0, M_ASHLAR)


# ---------------------------------------------------------------- the porticoes
def column(name, x, y, h, r, cap=True):
    cyl(name, x, y, 0.25, h - 0.3, r, r * 0.92, seg=16, m=M_PLASTER, caster=True)
    box(name + '_base', x - r - 0.12, x + r + 0.12, y - r - 0.12, y + r + 0.12, 0, 0.25, M_ASHLAR)
    if cap:
        box(name + '_cap', x - r - 0.15, x + r + 0.15, y - r - 0.15, y + r + 0.15, h - 0.3, h, M_ASHLAR, caster=True)

EAVE = 6.0
COL_H = 5.4
ROW_X = (-20.0, -17.5, -15.0, -12.5, -10.0)
for x in ROW_X:
    column(f'col_n_{x}', x, 6.0, COL_H, 0.3)
    column(f'col_s_{x}', x, -6.0, COL_H, 0.3)
for x in ROW_X:                                         # the north portico's second row (the hostage's at x -12.5)
    column(f'col_n2_{x}', x, 8.0, COL_H, 0.28)
for y in (-4.0, -2.0, 2.0, 4.0):
    column(f'col_w_{y}', -20.0, y, COL_H, 0.3)
    column(f'col_e_{y}', -10.0, y, COL_H, 0.3)

# entablature on the colonnades, a flat coffered ceiling under each portico roof, the tiled lean-to above
for s in (1, -1):
    y0, y1 = sorted((s * 5.75, s * 6.25))
    box(f'beam_ns{s}', -20.25, -9.75, y0, y1, COL_H, EAVE, M_ASHLAR, caster=True)
    y0, y1 = sorted((s * 5.75, s * YC))
    box(f'ceil_ns{s}', X0, X1, y0, y1, EAVE, EAVE + 0.25, M_PLASTER, caster=True, bottom=True)
for x, xa, xb in ((-20.0, X0, -19.75), (-10.0, -10.25, X1)):
    box(f'beam_we{x}', x - 0.25, x + 0.25, -5.75, 5.75, COL_H, EAVE, M_ASHLAR, caster=True)
    box(f'ceil_we{x}', xa, xb, -5.75, 5.75, EAVE, EAVE + 0.25, M_PLASTER, caster=True, bottom=True)
box('beam_n2', -20.25, -9.75, 7.75, 8.25, COL_H, EAVE, M_ASHLAR)

def lean_to(name, x0, x1, y_low, y_high, z_low, z_high):
    """a tiled roof plane from the eave line (y_low, z_low) up to the wall (y_high, z_high)"""
    bm = bmesh.new()
    a = bm.verts.new((x0, y_low, z_low)); b = bm.verts.new((x1, y_low, z_low))
    c = bm.verts.new((x1, y_high, z_high)); d = bm.verts.new((x0, y_high, z_high))
    f = bm.faces.new((a, b, c, d))
    if f.normal.z < 0:
        f.normal_flip()
    bm.normal_update(); bl.box_uv_bm(bm, 2.0)
    return bl.obj_from_bm(name, bm, [M_ROOF], 'arch', caster=True)

lean_to('roof_n', X0, X1, 5.6, YC, EAVE + 0.25, 7.6)
lean_to('roof_s', X0, X1, -5.6, -YC, EAVE + 0.25, 7.6)

def lean_to_x(name, x_low, x_high, y0, y1, z_low, z_high):
    bm = bmesh.new()
    a = bm.verts.new((x_low, y0, z_low)); b = bm.verts.new((x_low, y1, z_low))
    c = bm.verts.new((x_high, y1, z_high)); d = bm.verts.new((x_high, y0, z_high))
    f = bm.faces.new((a, b, c, d))
    if f.normal.z < 0:
        f.normal_flip()
    bm.normal_update(); bl.box_uv_bm(bm, 2.0)
    return bl.obj_from_bm(name, bm, [M_ROOF], 'arch', caster=True)

lean_to_x('roof_w', -19.6, X0, -5.6, 5.6, EAVE + 0.25, 7.6)
lean_to_x('roof_e', -10.4, X1, -5.6, 5.6, EAVE + 0.25, 7.6)

# the cistern's well-head in the middle of the courtyard
cyl('well', -15.0, 0.0, 0.0, 0.8, 0.9, 0.9, seg=20, m=M_ASHLAR, caster=True, cap_mat=M_WELL)


# ---------------------------------------------------------------- the throne hall
HX0, HX1 = HALL_X
WY = HALL_Y
TOP = HALL_H + 0.6
WIN_X = (-3.0, 1.0, 5.0, 9.0, 13.0)   # high windows, both long walls (castle.md 3.1)
WIN_Z = (6.3, 7.5)
WIN_W = 1.6

for s in (1, -1):
    yi, yo = sorted((s * WY, s * (WY + WALL)))
    box(f'hallwall_lo{s}', HX0 - WALL, HX1 + WALL, yi, yo, 0, WIN_Z[0], M_PLASTER, caster=True)
    box(f'hallwall_hi{s}', HX0 - WALL, HX1 + WALL, yi, yo, WIN_Z[1], TOP, M_PLASTER, caster=True)
    edges = [HX0 - WALL] + [v for c in WIN_X for v in (c - WIN_W / 2, c + WIN_W / 2)] + [HX1 + WALL]
    for k in range(0, len(edges), 2):
        box(f'hallpier{s}_{k}', edges[k], edges[k + 1], yi, yo, WIN_Z[0], WIN_Z[1], M_PLASTER, caster=True)
    for c in WIN_X:   # closed shutters, two leaves set in from the inside face, a hair of a gap between them
        ya, yb = sorted((s * (WY + 0.25), s * (WY + 0.4)))
        box(f'shutter{s}_{c}a', c - WIN_W / 2, c - 0.012, ya, yb, WIN_Z[0], WIN_Z[1], M_SHUTTER, caster=True)
        box(f'shutter{s}_{c}b', c + 0.012, c + WIN_W / 2, ya, yb, WIN_Z[0], WIN_Z[1], M_SHUTTER, caster=True)
    # the dark dado at the foot of the long walls (castle.md 3)
    di, do = sorted((s * (WY - 0.03), s * WY))
    box(f'dado{s}', HX0, HX1, di, do, 0, 1.2, M_DADO)
# east wall, with one high window over the curtain
box('hallwall_e', HX1, HX1 + WALL, -WY - WALL, -0.8, 0, TOP, M_PLASTER, caster=True)
box('hallwall_e2', HX1, HX1 + WALL, 0.8, WY + WALL, 0, TOP, M_PLASTER, caster=True)
box('hallwall_e3', HX1, HX1 + WALL, -0.8, 0.8, 0, 6.8, M_PLASTER, caster=True)
box('hallwall_e4', HX1, HX1 + WALL, -0.8, 0.8, 7.6, TOP, M_PLASTER, caster=True)
box('shutter_e', HX1 + 0.25, HX1 + 0.4, -0.8, 0.8, 6.8, 7.6, M_SHUTTER, caster=True)
box('dado_e', HX1 - 0.03, HX1, -WY, WY, 0, 1.2, M_DADO)
# west front with the 4 m door, 5 m high
box('hallfront_s', HX0 - WALL, HX0, -WY - WALL, -2.0, 0, TOP, M_PLASTER, caster=True)
box('hallfront_n', HX0 - WALL, HX0, 2.0, WY + WALL, 0, TOP, M_PLASTER, caster=True)
box('hallfront_lintel', HX0 - WALL, HX0, -2.0, 2.0, 5.0, TOP, M_PLASTER, caster=True)
box('door_frame_n', HX0 - WALL - 0.12, HX0 - WALL, 2.0, 2.5, 0, 5.4, M_ASHLAR)
box('door_frame_s', HX0 - WALL - 0.12, HX0 - WALL, -2.5, -2.0, 0, 5.4, M_ASHLAR)
box('door_frame_t', HX0 - WALL - 0.12, HX0 - WALL, -2.5, 2.5, 5.0, 5.4, M_ASHLAR)
for s in (1, -1):
    y0, y1 = sorted((s * 2.0, s * WY))
    box(f'dado_w{s}', HX0, HX0 + 0.03, y0, y1, 0, 1.2, M_DADO)
    # the door leaves, swung open against the inside of the front wall
    y0, y1 = sorted((s * 2.0, s * 4.0))
    box(f'doorleaf{s}', HX0 + 0.03, HX0 + 0.15, y0, y1, 0, 5.0, M_SHUTTER, caster=True)

# ceiling, its beams, and the pitched tile roof over it
lintel('hallceil', HX0 - WALL, HX1 + WALL, -WY - WALL, WY + WALL, HALL_H, TOP, M_PLASTER)   # no top: no attic floor
for x in (-3.5, 0.5, 5.5, 10.5, 14.5):
    box(f'hallbeam{x}', x - 0.2, x + 0.2, -WY, WY, HALL_H - 0.45, HALL_H, M_WOOD)

def pitched(name, x0, x1, y0, y1, z, ridge):
    bm = bmesh.new()
    a, b = bm.verts.new((x0, y0, z)), bm.verts.new((x1, y0, z))
    c, d = bm.verts.new((x1, y1, z)), bm.verts.new((x0, y1, z))
    r0, r1 = bm.verts.new((x0, (y0 + y1) / 2, ridge)), bm.verts.new((x1, (y0 + y1) / 2, ridge))
    bm.faces.new((a, b, r1, r0)); bm.faces.new((c, d, r0, r1))
    bm.normal_update(); bl.box_uv_bm(bm, 2.0)
    # 'far': lit live, not on the navmesh (its 19° slopes would be a floor over the dais, and nav.mjs takes the first
    # polygon over a nav root); the ceiling under it casts the hall's shadow
    bl.obj_from_bm(name, bm, [M_ROOF], 'far')
    bm = bmesh.new()
    for xx, flip in ((x0, True), (x1, False)):
        vs = [bm.verts.new(v) for v in ((xx, y0, z), (xx, y1, z), (xx, (y0 + y1) / 2, ridge))]
        bm.faces.new(vs[::-1] if flip else vs)
    bm.normal_update(); bl.box_uv_bm(bm, 3.0)
    bl.obj_from_bm(name + '_gable', bm, [M_PLASTER], 'arch', True)

pitched('hallroof', HX0 - WALL - 0.4, HX1 + WALL + 0.4, -WY - WALL - 0.4, WY + WALL + 0.4, TOP, TOP + 2.9)

# two rows of four columns, up to the ceiling
for x in (-2.0, 3.0, 8.0, 13.0):
    for y in (-4.0, 4.0):
        cyl(f'hallcol_{x}_{y}', x, y, 0.3, 6.2, 0.4, 0.36, seg=20, m=M_PLASTER, caster=True)
        box(f'hallcol_{x}_{y}_base', x - 0.58, x + 0.58, y - 0.58, y + 0.58, 0, 0.3, M_ASHLAR)
        box(f'hallcol_{x}_{y}_cap', x - 0.55, x + 0.55, y - 0.55, y + 0.55, 6.2, 6.5, M_ASHLAR)
for y in (-4.0, 4.0):   # the stone architrave on each row, carried to the end walls
    box(f'architrave{y}', HX0, HX1, y - 0.45, y + 0.45, 6.5, 7.1, M_ASHLAR, caster=True)

# the steps and the dais (three steps x 10..12, 0.9 m), the same polished stone
for k in range(3):
    box(f'step{k}', 10.0 + k * 2 / 3, HX1, -3.4, 3.4, 0, 0.3 * (k + 1), M_HALL, tile=3.0)
    box(f'stepedge{k}', 10.0 + k * 2 / 3 - 0.01, 10.0 + k * 2 / 3 + 0.06, -3.4, 3.4, 0.3 * (k + 1) - 0.04,
        0.3 * (k + 1) + 0.005, M_AXIS)

# the curtains: heavy folds behind the throne and either side of it on the east wall
def curtain(name, x, y0, y1, z0, z1, depth=0.14, pitch=0.35):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    n = max(2, int(round((y1 - y0) / pitch * 6)))
    cols = []
    for i in range(n + 1):
        y = y0 + (y1 - y0) * i / n
        dx = depth * (0.5 + 0.5 * math.sin(2 * math.pi * (y - y0) / pitch))
        cols.append((y, x - dx))
    V = [[bm.verts.new((xx, y, z)) for (y, xx) in cols] for z in (z0, z1)]
    L = 0.0
    us = [0.0]
    for (ya, xa), (yb, xb) in zip(cols, cols[1:]):
        L += math.hypot(yb - ya, xb - xa); us.append(L)
    for i in range(n):
        f = bm.faces.new((V[0][i + 1], V[0][i], V[1][i], V[1][i + 1]))   # facing -x, into the hall
        for l, uv in zip(f.loops, ((us[i + 1], z0), (us[i], z0), (us[i], z1), (us[i + 1], z1))):
            l[uvl].uv = (uv[0] / 2.0, uv[1] / 2.0)
        f.smooth = True
    bm.normal_update()
    return bl.obj_from_bm(name, bm, [M_CURTAIN], 'arch', caster=False)

curtain('curtain_throne', 15.6, -3.2, 3.2, 0.9, 6.4, depth=0.12, pitch=0.35)
box('curtain_rod', 15.45, 15.55, -3.4, 3.4, 6.4, 6.5, M_BRONZE)


# ---------------------------------------------------------------- the throne (its own node: not in the bake, not on the navmesh)
def throne(x, y):
    z = 0.9
    # castle.md 3.1: 1.6 m wide with the arms, 1.3 m deep, the seat 0.45 m and the back's top 1.9 m over the dais
    box('throne_seat', x - 0.55, x + 0.5, y - 0.62, y + 0.62, z, z + 0.4, M_THRONE, group='dyn')
    box('throne_cushion', x - 0.5, x + 0.48, y - 0.58, y + 0.58, z + 0.4, z + 0.47, M_CURTAIN, group='dyn')
    box('throne_back', x + 0.5, x + 0.72, y - 0.62, y + 0.62, z, z + 1.78, M_THRONE, group='dyn')
    box('throne_crest', x + 0.46, x + 0.76, y - 0.7, y + 0.7, z + 1.72, z + 1.9, M_BRONZE, group='dyn')
    for s in (1, -1):
        y0, y1 = sorted((y + s * 0.62, y + s * 0.8))
        box(f'throne_arm{s}', x - 0.58, x + 0.72, y0, y1, z, z + 0.78, M_THRONE, group='dyn')
        box(f'throne_knob{s}', x - 0.62, x - 0.5, y0 - 0.02, y1 + 0.02, z + 0.72, z + 0.86, M_BRONZE, group='dyn')
    box('throne_stool', x - 1.05, x - 0.6, y - 0.4, y + 0.4, z, z + 0.16, M_THRONE, group='dyn')

throne(*LAYOUT['spots']['king-throne']['at'])


# ---------------------------------------------------------------- lamps and braziers, and their lights
WARM = (1.0, 0.5, 0.17)   # about 1900 K, linear (castle.md 5.1)

def light(name, x, y, z, watts, size):
    ld = bpy.data.lights.new(name, 'POINT')
    ld.energy = watts
    ld.color = WARM
    ld.shadow_soft_size = size
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = (x, y, z)

# the lamps' own bronze is in the 'far' group: not baked (the light sits right on it and would set the lightmap's
# range, leaving the walls a few levels of it), lit live like the people
def brazier(name, x, y, z):
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.3
        rod(f'{name}_leg{k}', (x + 0.38 * math.cos(a), y + 0.38 * math.sin(a), 0.0),
            (x + 0.16 * math.cos(a), y + 0.16 * math.sin(a), z - 0.35), 0.03, M_BRONZE, group='far')
    cyl(f'{name}_bowl', x, y, z - 0.25, z, 0.14, 0.3, seg=18, m=M_BRONZE, group='far', cap=True, cap_mat=M_EMBER)

def wall_lamp(name, x, y, z):
    """an oil lamp on an iron bracket out from the wall (y = ±7): dim, so the west half of the hall is not dead black"""
    w = math.copysign(HALL_Y, y)
    rod(f'{name}_bracket', (x, w, z - 0.25), (x, y, z - 0.05), 0.02, M_BRONZE, group='far', seg=5)
    cyl(f'{name}_cup', x, y, z - 0.08, z + 0.02, 0.05, 0.09, seg=10, m=M_BRONZE, group='far', cap_mat=M_EMBER)

def chandelier(name, x, y, z, cups, radius):
    seg = 24
    for k in range(seg):   # the ring
        a0, a1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg
        rod(f'{name}_ring{k}', (x + radius * math.cos(a0), y + radius * math.sin(a0), z),
            (x + radius * math.cos(a1), y + radius * math.sin(a1), z), 0.035, M_BRONZE, group='far', seg=6)
    for k in range(3):   # chains up to the ceiling beam
        a = 2 * math.pi * k / 3
        rod(f'{name}_chain{k}', (x + radius * math.cos(a), y + radius * math.sin(a), z),
            (x, y, HALL_H - 0.45), 0.012, M_BRONZE, group='far', seg=5)
    for k in range(cups):
        a = 2 * math.pi * (k + 0.5) / cups
        cx, cy = x + radius * math.cos(a), y + radius * math.sin(a)
        cyl(f'{name}_cup{k}', cx, cy, z - 0.05, z + 0.06, 0.05, 0.1, seg=10, m=M_BRONZE, group='far', cap_mat=M_EMBER)

for lamp in LAYOUT['lamps']:
    (x, y), z = lamp['at'], lamp['z']
    if lamp['kind'] == 'chandelier':
        chandelier(lamp['id'], x, y, z, lamp['cups'], lamp['radius'])
        for k in range(lamp['cups']):
            a = 2 * math.pi * (k + 0.5) / lamp['cups']
            light(f"{lamp['id']}_light{k}", x + lamp['radius'] * math.cos(a), y + lamp['radius'] * math.sin(a), z + 0.18,
                  lamp['watts'], 0.08)
    elif lamp['kind'] == 'wall':
        wall_lamp(lamp['id'], x, y, z)
        light(f"{lamp['id']}_light", x, y, z + 0.2, lamp['watts'], 0.1)
    else:
        brazier(lamp['id'], x, y, z)
        light(f"{lamp['id']}_light", x, y, z + 0.4, lamp['watts'], 0.3)


# ---------------------------------------------------------------- the tower behind the hall's north-east corner
box('tower', 16.8, 22.0, 8.0, 14.0, 0, 30.0, M_ASHLAR, caster=True)
for i, (x0, x1, y0, y1) in enumerate(((16.8, 18.0, 8.0, 8.6), (19.4, 20.6, 8.0, 8.6), (16.8, 18.0, 13.4, 14.0),
                                      (19.4, 20.6, 13.4, 14.0), (16.8, 17.4, 10.2, 11.8), (21.4, 22.0, 10.2, 11.8))):
    box(f'merlon{i}', x0, x1, y0, y1, 30.0, 31.2, M_ASHLAR, caster=True)
box('tower_cornice', 16.6, 22.2, 7.8, 14.2, 29.6, 30.0, M_ASHLAR)

# the dyn objects become one node, 'throne' (bake.py exports dyn objects as they are)
dyn = [o for o in bl.COLL['dyn'].objects]
bpy.ops.object.select_all(action='DESELECT')
for o in dyn:
    o.select_set(True)
bpy.context.view_layer.objects.active = dyn[0]
bpy.ops.object.join()
j = bpy.context.view_layer.objects.active
j.name = 'throne'; j.data.name = 'throne'

# bl.save's per-group counts expect meshes only; the lights sit in the scene's own collection
bpy.ops.wm.save_as_mainfile(filepath=f'{OUT}/{STEM}_raw.blend')
print('GROUPS', {n: len(c.objects) for n, c in bl.COLL.items()}, 'lights', len(bpy.data.lights))
