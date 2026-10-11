# The village (F-11, ux/scenes/village.md): Melos's home, the groom's house, the well, two neighbours, the threshing
# floor, the fields, the pasture and the far land, for the first visit's light (day 1, 10:00, clear).
# Plan frame (village.md 1): metres, +x = east (azimuth 90°, the road to Syracuse), +y = north, the lane at z = 0.
# No rotation (layout rotationDeg 0), so the sun scripts get SCENE_MINUS_X_AZ = 270.
# Groups as bake.py expects them (../common/bl.py). Besides those, the instanced things (wheat, sheaves, vines, sheep)
# are written to <stem>_inst.json (one prototype each, a transform per copy) and their prototypes to <stem>_proto.glb;
# merge_inst.mjs adds them to the baked glTF as EXT_mesh_gpu_instancing nodes. In the bake the copies stand in the
# 'inst' collection as linked duplicates, so the ground gets their occlusion; they are not baked themselves.
import bpy, os, sys, math, random, json   # bpy first: it brings mathutils
from mathutils import Vector, Matrix, noise
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import bl
from bl import box, cyl, rod, rock, tree, gable, heightfield, lines

OUT = os.environ['PLAZA_OUT']
STEM = os.environ['SCENE_STEM']
random.seed(11)
bl.setup(f'{OUT}/tex')
mat, pbr, tex_exists = bl.mat, bl.pbr, bl.tex_exists

# ---------------------------------------------------------------- materials (texture keys: ../common/road_tex.py)
M_ROAD = pbr('floor', 'road')       # named floor: the page's ambient ground colour reads materials.floor
M_EARTH = pbr('earth', 'earth')     # the beaten earth of the yards
M_GRASS = pbr('grass', 'grass')
M_STUBBLE = mat('stubble', tex_exists('stubble_base'), None, tex_exists('stubble_mr'))   # no normal map: flat, seen from afar; its 0.3 MB kept the final entry pack within 3.5 MB
M_ROCK = pbr('outcrop', 'outcrop')  # dry-stone walls, the threshing floor's slabs and kerb
M_PLASTER = pbr('mudplaster', 'mudplaster')   # rough stone walls under an earthy lime plaster (village.md 6.2)
M_ROOF = mat('roofwarm', tex_exists('roofwarm_base'), None, None, rough=0.8)   # old tiles, faded orange-brown
M_THATCH = pbr('thatch', 'thatch')
M_WOOD = pbr('wood', 'wood')
M_BARK = mat('bark', tex_exists('bark_base'), tex_exists('wood_nrm'), None, rough=0.9)
M_FIGBARK = mat('figbark', color=(0.52, 0.5, 0.46), rough=0.7)   # grey-white and smooth
M_POPLAR = mat('poplar', tex_exists('poplar_base'), None, None, rough=0.8)
M_HOLM = mat('holmoak', tex_exists('holmoak_base'), None, None, rough=0.85)
M_FIG = mat('fig', tex_exists('fig_base'), None, None, rough=0.75)
M_VINE = mat('vine', tex_exists('vine_base'), None, None, rough=0.75)
M_WHEAT = mat('wheat', tex_exists('wheat_base'), None, None, rough=0.85)
M_SHEAF = mat('sheaf', tex_exists('thatch_base'), None, None, rough=0.9)
M_WOOL = mat('wool', color=(0.78, 0.74, 0.66), rough=0.95)       # the copies get a little colour each (merge_inst)
M_HILL = mat('hill', tex_exists('hill_base'), tex_exists('outcrop_nrm'), None, rough=0.95)
M_HAY = mat('hay', tex_exists('thatch_base'), None, None, rough=0.95)
M_POT = mat('pot', color=(0.56, 0.36, 0.24), rough=0.7)           # terracotta: the well's jar, the altar's bowls


# ---------------------------------------------------------------- the ground
def ss(x, a, b):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)

TH = (-26.0, -10.0)        # the threshing floor: a round of flat slabs 1.5 m above the lane (village.md 2)
TH_R, TH_Z = 5.3, 1.5
PATH = ((-24.1, 0.6), (-24.3, -5.2))   # the path up to it from the lane

def path_w(x, y):
    """0..1: on the path up to the threshing floor (a ramp 1.8 m wide from the lane to the floor's edge)"""
    (x0, y0), (x1, y1) = PATH
    t = (y - y0) / (y1 - y0)
    if not -0.1 <= t <= 1.1:
        return 0.0, t
    xc = x0 + (x1 - x0) * min(1, max(0, t))
    return 1 - ss(abs(x - xc), 0.9, 1.6), t

def terrain(x, y):
    # the village ground: nearly flat, a little roll off the lane and the yards
    roll = 0.25 * noise.noise(Vector((x / 9, y / 9, 0.7)))
    lane = 1 - ss(abs(y - 2.0), 1.6, 3.0)
    yards = 1.0 if (-14.5 < x < 12.5 and -14.5 < y < 4.0) or (-32.5 < x < -17.5 and 4.5 < y < 18.5) else 0.0
    z = roll * (1 - lane) * (1 - yards) * ss(math.hypot(x - 4, y - 4.5), 2.5, 5)
    # the threshing floor: flat on top, falling away in a short bank
    d = math.hypot(x - TH[0], y - TH[1])
    hump = 1 - ss(d, TH_R, TH_R + 2.6)
    w, t = path_w(x, y)
    ramp = TH_Z * min(1, max(0, t)) * w
    return max(z, TH_Z * hump, ramp) if d < TH_R + 3 or w > 0 else z

def in_rect(x, y, x0, x1, y0, y1):
    return x0 <= x <= x1 and y0 <= y <= y1

FIELD_SE = (14, 36, -26, -3)
FIELD_SW = (-36, -16, -26, -16)
CUT_Y = -10.5      # the south-east field is reaped north of this line (stubble and sheaves); wheat stands south of it

def ground_mat(cx, cy, cz):
    if math.hypot(cx - TH[0], cy - TH[1]) < TH_R:
        return 4
    if 0.5 <= cy <= 3.5 or path_w(cx, cy)[0] > 0.5:
        return 0
    if in_rect(cx, cy, -14, 2, -14, -0.5) or in_rect(cx, cy, -32, -18, 5, 13) or in_rect(cx, cy, 2, 12, -14, -3):
        return 1
    if in_rect(cx, cy, -18, 6, 3.5, 6.6) or in_rect(cx, cy, 2.5, 6, -3.0, 0.5):
        return 1     # the trodden ground by the well and the neighbours, and before the pen gate
    if in_rect(cx, cy, *FIELD_SE) or in_rect(cx, cy, *FIELD_SW):
        return 3
    return 2

GMATS = [M_ROAD, M_EARTH, M_GRASS, M_STUBBLE, M_ROCK]
# 1 m where people walk and the ground has edges (the yards, the lane, the threshing floor), 2 m over the fields,
# the pasture and the margins
XS = lines((-44, -34, 2.0), (-34, 14, 1.0), (14, 48, 2.0), extra=(-24.1, -23.2, -25.0, 2.0, 12.0, 6.0, 36.0, 32.0, 12.4))
YS = lines((-34, -18, 2.0), (-18, 6, 1.0), (6, 34, 2.0), extra=(0.5, 3.5, -0.5, 2.0, -26.0, -16.0, -3.0, 13.0, 18.0, 24.0))
heightfield('ground', XS, YS, terrain, ground_mat, GMATS, 'ground', tile=3.0)


# ---------------------------------------------------------------- the far land (village.md 2, 远景)
def far_height(x, y):
    """west: the Hyblaean ridge the sun sets behind (the skyline 4〜6° from the threshing floor); north and south: long
    slopes with olive terraces; east: the road runs into low hills towards the next village"""
    d = math.hypot(x, y)
    if d < 46:
        return terrain(x, y)
    a = math.atan2(y, x)
    west = max(0.0, -math.cos(a))
    east = max(0.0, math.cos(a))
    side = abs(math.sin(a))
    n = noise.noise(Vector((x / 70, y / 70, 1.3))) * 0.5 + 0.5
    n2 = noise.noise(Vector((x / 22, y / 22, 4.4)))
    rag = noise.noise(Vector((math.cos(a) * 3, math.sin(a) * 3, 8.8)))
    deg = 1.2 + 4.5 * west ** 1.5 * (1 + 0.35 * rag) + 2.2 * side * (0.7 + 0.5 * n) + 1.0 * east
    road = 1 - 0.6 * (1 - ss(abs(y - 2), 6, 22)) * ss(x, 40, 90)    # the road east keeps a shallow cut
    return d * math.tan(math.radians(deg)) * ss(d, 46, 220) * (0.85 + 0.2 * n + 0.06 * n2) * road

def far_mat(cx, cy, cz):
    return 1 if cz > 6 else 0

FX = lines((-420, -120, 30.0), (-120, 120, 10.0), (120, 420, 30.0), extra=(-44, 48))
FY = lines((-420, -120, 30.0), (-120, 120, 10.0), (120, 420, 30.0), extra=(-34, 34))
heightfield('far_land', FX, FY, far_height, far_mat, [M_GRASS, M_HILL], 'far',
            skip=lambda cx, cy: -44 < cx < 48 and -34 < cy < 34, tile=12.0, tris=True)

def far_road():
    """the road east past the near ground, laid 12 cm over the far land"""
    import bmesh
    bm = bmesh.new()
    prev = None
    for x in lines((48, 260, 4.0)):
        y = 2.0 + 10 * ss(x, 60, 160) * math.sin((x - 48) / 40)
        pair = [bm.verts.new((x, y + k * 1.5, bl.grid_height(FX, FY, far_height, x, y + k * 1.5) + 0.12)) for k in (-1, 1)]
        if prev:
            bm.faces.new((prev[0], pair[0], pair[1], prev[1]))
        prev = pair
    bm.normal_update()
    bl.box_uv_bm(bm, 3.0)
    bl.obj_from_bm('far_road', bm, [M_ROAD], 'far')
far_road()


# ---------------------------------------------------------------- dry-stone walls (village.md 6.2: no mortar)
def drystone(name, a, b, height, seed, width=0.55, caster=True):
    """a wall of rough stones from a to b (plan), in courses about 0.5 m high, the top ragged; each stone its own
    coarse lump, smooth shaded (faceted they read as crystals). caster: also in the shadow proxy (the 1.8 m walls)"""
    rr = random.Random(seed)
    a, b = Vector((a[0], a[1], 0)), Vector((b[0], b[1], 0))
    L0 = (b - a).length
    if L0 < 0.3:
        return
    u = (b - a) / L0
    n = Vector((-u.y, u.x, 0))
    courses = max(1, round(height / 0.5))
    hc = height / courses
    import bmesh
    bm = bmesh.new()
    for c in range(courses):
        s = 0.0 if c % 2 == 0 else rr.uniform(0.15, 0.35)
        while s < L0 - 0.15:
            L = min(rr.uniform(0.6, 1.0), L0 - s)
            p = a + u * (s + L / 2)
            g = terrain(p.x, p.y)
            top = g + (c + 1) * hc + (rr.uniform(-0.06, 0.04) if c == courses - 1 else 0.0)
            bot = g + c * hc - (0.25 if c == 0 else 0.06)
            w = width * rr.uniform(0.85, 1.0) * (1 - 0.12 * c / courses)
            g_ = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
            seed_ = seed * 100 + c * 37 + int(s * 10)
            for v in g_['verts']:
                q = v.co.copy()
                k = 1 + 0.18 * noise.noise(q * 1.4 + Vector((seed_, 0.3, 1.1)))
                ex = q.x * k * L / 2 * 1.06
                ey = q.y * k * w / 2
                ez = (q.z * k + 1) / 2
                v.co = p + u * ex + n * (ey + rr.uniform(-0.01, 0.01)) + Vector((0, 0, bot + ez * (top - bot)))
            s += L * rr.uniform(0.92, 1.0)
    for f in bm.faces:
        f.smooth = True
    bm.normal_update()
    bl.box_uv_bm(bm, 1.5)
    bl.obj_from_bm(name, bm, [M_ROCK], 'arch', caster)

def wall_run(name, pts, height, seed, gaps=(), caster=True):
    """dry-stone walls along a polyline, leaving gaps [(x0, y0, x1, y1)] (gates)"""
    k = 0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        segs = [((x0, y0), (x1, y1))]
        for gx0, gy0, gx1, gy1 in gaps:
            nxt = []
            for (ax, ay), (bx, by) in segs:
                if ay == by and gy0 <= ay <= gy1 and min(ax, bx) < gx1 and max(ax, bx) > gx0:
                    lo, hi = min(ax, bx), max(ax, bx)
                    nxt += [((lo, ay), (gx0, ay)), ((gx1, ay), (hi, ay))]
                elif ax == bx and gx0 <= ax <= gx1 and min(ay, by) < gy1 and max(ay, by) > gy0:
                    lo, hi = min(ay, by), max(ay, by)
                    nxt += [((ax, lo), (ax, gy0)), ((ax, gy1), (ax, hi))]
                else:
                    nxt.append(((ax, ay), (bx, by)))
            segs = nxt
        for a, b in segs:
            drystone(f'{name}{k}', a, b, height, seed + k, caster=caster)
            k += 1

# Melos's yard: x -14..2, y -14..-0.5, 1.8 m; the gate in the north wall x -7.5..-5.5; the narrow way into the pen in the
# east wall at y -11.5..-10.5; the house's walls stand in for the yard wall along its south and west
wall_run('yardwall', [(-14, -8.5), (-14, -0.5), (2, -0.5), (2, -14), (-2, -14)], 1.8, 100,
         gaps=((-7.5, -0.6, -5.5, -0.4), (1.9, -11.5, 2.1, -10.5)))
# the sheep pen: x 2..12, y -14..-3, 1.2 m, the gate on the road at x 6.2..7.8; its south wall runs on behind the fold
wall_run('penwall', [(2, -3), (12, -3), (12, -14), (7, -14)], 1.2, 200, gaps=((6.2, -3.1, 7.8, -2.9),), caster=False)
# the pasture: x 6..32, y 3.7..24, 1.2 m, the gate at x 9..11 on the lane
wall_run('pasturewall', [(6, 3.7), (32, 3.7), (32, 24), (6, 24), (6, 3.7)], 1.2, 300, gaps=((9, 3.6, 11, 3.8),),
         caster=False)   # the low walls: not in the shadow proxy (its triangles), their baked occlusion stays
# the groom's yard: x -32..-18, y 5..13, 1.8 m (his house closes it on the north), the gate at x -22..-20
wall_run('groomwall', [(-32, 13), (-32, 5.2), (-18, 5.2), (-18, 13)], 1.8, 400, gaps=((-22, 5.1, -20, 5.3),))


# ---------------------------------------------------------------- houses (village.md 2, 3)
def house(name, x0, x1, y0, y1, eave, door=None, windows=(), shed=None, t=0.5):
    """rough stone walls under earth plaster, 0.5 m thick, the floor at ground level. door: (side, centre, width, height);
    windows: [(side, centre, z0, z1, width)]; side is 'n', 's', 'e' or 'w'. shed: a single-pitch roof falling to that
    side (Melos's house falls to the north, the yard), else a gable along x"""
    z0 = min(terrain(x, y) for x in (x0, x1) for y in (y0, y1)) - 0.3
    holes = {'n': [], 's': [], 'e': [], 'w': []}
    if door:
        holes[door[0]].append((door[1] - door[2] / 2, door[1] + door[2] / 2, z0, door[3]))
    for side, c, wz0, wz1, w in windows:
        holes[side].append((c - w / 2, c + w / 2, wz0, wz1))
    hi = eave + (y1 - y0) * 0.22 if shed else eave
    def wall(side, a0, a1, top):
        cuts = sorted(holes[side])
        pts = [a0]
        for c0, c1, hz0, hz1 in cuts:
            pts += [c0, c1]
        pts.append(a1)
        k = 0
        for s0, s1 in zip(pts[0::2], pts[1::2]):
            if s1 - s0 > 0.01:
                seg(side, s0, s1, z0, top(s0, s1), k); k += 1
        for c0, c1, hz0, hz1 in cuts:
            if hz0 > z0 + 0.05:
                seg(side, c0, c1, z0, hz0, k); k += 1
            seg(side, c0, c1, hz1, top(c0, c1), k); k += 1
    def seg(side, s0, s1, za, zb, k):
        if side in 'ns':
            y = y1 if side == 'n' else y0
            box(f'{name}_{side}{k}', s0, s1, y - t / 2, y + t / 2, za, zb, M_PLASTER, tile=3.0, caster=True)
        else:
            x = x1 if side == 'e' else x0
            box(f'{name}_{side}{k}', x - t / 2, x + t / 2, s0, s1, za, zb, M_PLASTER, tile=3.0, caster=True)
    if shed:   # the roof falls from the south wall (hi) to the north (eave)
        zs = lambda yy: hi + (eave - hi) * (yy - y0) / (y1 - y0)
        wall('n', x0 - t / 2, x1 + t / 2, lambda a, b: eave)
        wall('s', x0 - t / 2, x1 + t / 2, lambda a, b: hi)
        for side, x in (('w', x0), ('e', x1)):
            box(f'{name}_{side}base', x - t / 2, x + t / 2, y0 + t / 2, y1 - t / 2, z0, eave, M_PLASTER, tile=3.0, caster=True)
            import bmesh
            bm = bmesh.new()
            vs = [bm.verts.new(v) for v in [(x - t / 2, y0 + t / 2, eave), (x - t / 2, y1 - t / 2, eave),
                                             (x - t / 2, y0 + t / 2, zs(y0 + t / 2)),
                                             (x + t / 2, y0 + t / 2, eave), (x + t / 2, y1 - t / 2, eave),
                                             (x + t / 2, y0 + t / 2, zs(y0 + t / 2))]]
            bm.faces.new((vs[0], vs[2], vs[1])); bm.faces.new((vs[3], vs[4], vs[5]))
            bm.faces.new((vs[0], vs[3], vs[5], vs[2])); bm.faces.new((vs[2], vs[5], vs[4], vs[1]))
            bm.normal_update(); bl.box_uv_bm(bm, 3.0)
            bl.obj_from_bm(f'{name}_{side}top', bm, [M_PLASTER], 'arch', True)
        o = 0.45
        import bmesh
        bm = bmesh.new()
        vs = [bm.verts.new(v) for v in [(x0 - o, y0 - o, zs(y0 - o)), (x1 + o, y0 - o, zs(y0 - o)),
                                         (x1 + o, y1 + o, zs(y1 + o)), (x0 - o, y1 + o, zs(y1 + o))]]
        bm.faces.new(vs)
        top = [bm.verts.new(v.co + Vector((0, 0, 0.12))) for v in vs]
        bm.faces.new(top[::-1])
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((vs[i], top[i], top[j], vs[j]))
        bm.normal_update(); bl.box_uv_bm(bm, 2.0)
        bl.obj_from_bm(f'{name}_roof', bm, [M_ROOF], 'arch', True)
    else:
        for side in 'ns':
            wall(side, x0 - t / 2, x1 + t / 2, lambda a, b: eave)
        for side in 'ew':
            wall(side, y0 + t / 2, y1 - t / 2, lambda a, b: eave)
        gable_x(name, x0 - t / 2, x1 + t / 2, y0 - t / 2, y1 + t / 2, eave)
    return z0

def gable_x(name, x0, x1, y0, y1, z, pitch=24, over=0.4):
    """a tiled gable roof with its ridge along x (the long side), and its two gable walls"""
    tp = math.tan(math.radians(pitch))
    X0, X1, Y0, Y1 = x0 - over, x1 + over, y0 - over, y1 + over
    ym = (Y0 + Y1) / 2; rz = z + (Y1 - Y0) / 2 * tp
    import bmesh
    bm = bmesh.new()
    a, b, c, d = [bm.verts.new(v) for v in [(X0, Y0, z), (X1, Y0, z), (X1, ym, rz), (X0, ym, rz)]]
    e, f, g, h = [bm.verts.new(v) for v in [(X1, Y1, z), (X0, Y1, z), (X0, ym, rz), (X1, ym, rz)]]
    bm.faces.new((a, b, c, d)); bm.faces.new((e, f, g, h))
    bm.normal_update(); bl.box_uv_bm(bm, 2.0)
    bl.obj_from_bm(name + '_roof', bm, [M_ROOF], 'arch', True)
    bm = bmesh.new()
    zr = z + (y1 - y0) / 2 * tp
    for xx, flip in [(x0, True), (x1, False)]:
        vs = [bm.verts.new(v) for v in [(xx, y0, z), (xx, y1, z), (xx, (y0 + y1) / 2, zr)]]
        bm.faces.new(vs[::-1] if flip else vs)
    bm.normal_update(); bl.box_uv_bm(bm, 3.0)
    bl.obj_from_bm(name + '_gable', bm, [M_PLASTER], 'arch', True)

# Melos's house: x -14..-2, y -14..-8.5 (the walls' centre lines), eaves 3 m at the yard (north), a single-pitch roof;
# the door at (-8, -8.5) and two shuttered windows in the north wall; inside a floor of beaten earth (the ground)
house('melos', -14, -2, -14, -8.5, 3.0, door=('n', -8.0, 1.1, 2.1), shed=True,
      windows=(('n', -11.5, 1.2, 1.9, 0.7), ('n', -4.5, 1.2, 1.9, 0.7)))
for i, (cx, ang) in enumerate(((-11.5, 100), (-4.5, 75))):   # the shutters, open against the wall
    for s in (-1, 1):
        hx = cx + s * 0.35
        xf = Matrix.Translation((hx, -8.25, 0)) @ Matrix.Rotation(math.radians(-s * ang), 4, 'Z') @ Matrix.Translation((-hx, 8.25, 0))
        box(f'shutter{i}{s}', min(hx, hx - s * 0.35), max(hx, hx - s * 0.35), -8.25, -8.2, 1.2, 1.9, M_WOOD, tile=1.0,
            xform=xf)
box('melos_door', -8.55, -8.47, -8.2, -7.2, 0.0, 2.08, M_WOOD, tile=1.0, caster=True)    # the door leaf, open out into the yard
box('melos_lintel', -8.7, -7.3, -8.85, -8.15, 2.1, 2.3, M_WOOD, tile=1.0, caster=True)
# the neighbours (outside only, village.md 2)
house('nbA', -12, -4, 5, 11, 3.0, door=('s', -8, 1.0, 2.0), windows=(('s', -5.5, 1.3, 1.9, 0.6),))
house('nbB', -2, 4, 7, 12, 2.8, door=('s', 1.0, 1.0, 2.0))
# the groom's house: x -32..-20, y 13..18, the door on the yard (south)
house('groom', -32, -20, 13, 18, 3.0, door=('s', -26, 1.1, 2.1), windows=(('s', -22.5, 1.3, 1.9, 0.6),
                                                                           ('s', -29.5, 1.3, 1.9, 0.6)))

# the altar in the middle of the yard (village.md 2): a stone block 1.2 × 0.8 m, 1 m high, with a step
box('altar', -6.6, -5.4, -4.9, -4.1, -0.2, 1.0, M_ROCK, tile=1.0, caster=True)
box('altar_top', -6.7, -5.3, -5.0, -4.0, 1.0, 1.08, M_ROCK, tile=1.0, caster=True)
box('altar_step', -6.8, -5.2, -5.1, -3.9, -0.2, 0.12, M_ROCK, tile=1.0)

# ---------------------------------------------------------------- what the page shows by the clock (card 1, 5): own
# nodes in 'dyn' (not baked), found by name in the page (three/village/VillageLife.tsx)
M_MYRTLE = mat('myrtle', color=(0.16, 0.26, 0.12), rough=0.7)    # dark glossy myrtle leaves
M_GLOW = mat('doorglow', color=(0.0, 0.0, 0.0), rough=1.0)       # the page draws it as added warm light


def node(name, objs):
    """join objs into one object named name, moved to the 'dyn' collection"""
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = o.data.name = name
    for c in list(o.users_collection):
        c.objects.unlink(o)
    bl.coll('dyn').objects.link(o)
    o['caster'] = 0
    return o


def leaf_quads(name, spots, size, m, z, seed):
    """small flat leaves lying on the ground: one quad each at (x, y), random turn"""
    import bmesh
    r = random.Random(seed)
    bm = bmesh.new()
    for x, y in spots:
        a = r.uniform(0, math.pi)
        c, s_ = math.cos(a), math.sin(a)
        l, w = size * r.uniform(0.8, 1.2), size * 0.45
        q = [(x + c * dx - s_ * dy, y + s_ * dx + c * dy, z + r.uniform(0, 0.004))
             for dx, dy in ((-l, -w), (l, -w), (l, w), (-l, w))]
        bm.faces.new([bm.verts.new(p) for p in q])
    bm.normal_update(); bl.box_uv_bm(bm, 0.2)
    return bl.obj_from_bm(name, bm, [m], 'dyn')


# the altar dressed for the wedding (beat.09 「神々の祭壇を飾り」, from 一日目 10:30): myrtle garlands along the top's
# edges and hanging in swags at the front, three bowls on the top
_dress = []
for i, (a, b) in enumerate((((-6.7, -5.0), (-5.3, -5.0)), ((-5.3, -5.0), (-5.3, -4.0)), ((-5.3, -4.0), (-6.7, -4.0)),
                            ((-6.7, -4.0), (-6.7, -5.0)))):
    _dress.append(rod(f'garland{i}', Vector((*a, 1.1)), Vector((*b, 1.1)), 0.045, M_MYRTLE))
for i, x in enumerate((-6.6, -6.0, -5.4)):
    for side, y in (('s', -5.03), ('n', -3.97)):
        _dress.append(rod(f'swag{i}{side}a', Vector((x, y, 1.06)), Vector((x + 0.3, y, 0.82)), 0.035, M_MYRTLE))
        _dress.append(rod(f'swag{i}{side}b', Vector((x + 0.3, y, 0.82)), Vector((x + 0.6, y, 1.06)), 0.035, M_MYRTLE))
for i, x in enumerate((-6.4, -6.0, -5.6)):
    _dress.append(cyl(f'altarbowl{i}', x, -4.5, 1.08, 1.16, 0.07, 0.11, 10, M_POT))
node('altar-dressing', _dress)

# myrtle leaves strewn over the yard on the wedding day (from 二日目 06:00): thick round the altar, along the way from
# the gate (x -7.5..-5.5 on the north wall) and before the house door
_r = random.Random(23)
_spots = []
while len(_spots) < 700:
    x, y = _r.uniform(-13.5, 1.5), _r.uniform(-8.1, -1.0)
    near = max(math.exp(-((x + 6.0) ** 2 + (y + 4.5) ** 2) / 6.0), math.exp(-((x + 6.5) ** 2) / 1.5) * (y > -4.0),
               math.exp(-((x + 8.0) ** 2 + (y + 7.3) ** 2) / 1.2))
    if _r.random() < 0.08 + 0.92 * near:
        _spots.append((x, y))
leaf_quads('myrtle-leaves', _spots, 0.035, M_MYRTLE, 0.006, 5)

# the house's warm door on the rainy wedding night (二日目 18:30 to 三日目 06:00, village.md 5.1): the light spilling
# from the open door onto the wet ground, and the two windows' shutters glowing at their cracks; flat, facing out,
# drawn by the page as added light (nothing by day)
import bmesh
_bm = bmesh.new()
for q in ([(-8.6, -8.24, 0.012), (-7.4, -8.24, 0.012), (-7.2, -6.4, 0.012), (-8.8, -6.4, 0.012)],
          [(-11.85, -8.235, 1.2), (-11.15, -8.235, 1.2), (-11.15, -8.235, 1.9), (-11.85, -8.235, 1.9)],
          [(-4.85, -8.235, 1.2), (-4.15, -8.235, 1.2), (-4.15, -8.235, 1.9), (-4.85, -8.235, 1.9)]):
    f = _bm.faces.new([_bm.verts.new(p) for p in q])
    f.normal_update()
    if f.normal.z < 0.5 and f.normal.y < 0.5:   # the windows face north (out), the spill up
        f.normal_flip()
_bm.normal_update(); bl.box_uv_bm(_bm, 1.0)
bl.obj_from_bm('door-glow', _bm, [M_GLOW], 'dyn')

# the sheepfold: stone walls on the south, east and west, open to the north (the pen), a thatched lean-to roof,
# hay inside (village.md 2: seen from outside)
for i, (x0, x1, y0, y1) in enumerate(((2.0, 7.0, -14.0, -13.6), (2.0, 2.4, -13.6, -10.2), (6.8, 7.2, -13.6, -10.2))):
    box(f'fold_wall{i}', x0, x1, y0, y1, -0.2, 2.2 if i == 0 else 1.7, M_ROCK, tile=1.5, caster=True)
for i, x in enumerate((2.2, 4.6, 7.0)):
    cyl(f'fold_post{i}', x, -10.2, -0.2, 2.0, 0.08, 0.07, 7, M_WOOD, caster=True)
import bmesh
_bm = bmesh.new()
_v = [_bm.verts.new(v) for v in [(1.7, -14.3, 2.35), (7.5, -14.3, 2.35), (7.5, -9.8, 1.85), (1.7, -9.8, 1.85)]]
_bm.faces.new(_v)
_t = [_bm.verts.new(v.co + Vector((0, 0, 0.18))) for v in _v]
_bm.faces.new(_t[::-1])
for i in range(4):
    j = (i + 1) % 4
    _bm.faces.new((_v[i], _t[i], _t[j], _v[j]))
_bm.normal_update(); bl.box_uv_bm(_bm, 1.5)
bl.obj_from_bm('fold_roof', _bm, [M_THATCH], 'arch', True)
box('hay', 2.5, 6.7, -13.5, -11.2, -0.1, 0.35, M_HAY, group='far', tile=1.0)   # not navmesh input: melos-hut is in it

# the well (village.md 2): a round stone curb, a wooden frame and a bucket; a water jar beside it
cyl('well_curb', 4.0, 4.35, -0.2, 0.8, 0.72, 0.7, 16, M_ROCK, caster=True)
for s in (-1, 1):
    cyl(f'well_post{s}', 4.0 + 0.62 * s, 4.35, 0.75, 2.0, 0.06, 0.05, 6, M_WOOD, caster=True)
rod('well_beam', (3.3, 4.35, 1.95), (4.7, 4.35, 1.95), 0.05, M_WOOD, caster=True)
cyl('well_bucket', 3.55, 3.95, 0.8, 1.05, 0.15, 0.17, 8, M_WOOD, group='far')
cyl('well_jar', 4.95, 3.75, 0.0, 0.55, 0.16, 0.12, 10, M_POT, group='far')

# the vine arbour in the groom's yard (village.md 2): x -30..-22, y 7..11.5, 2.4 m; a table and two benches under it
# (furniture in the far group: not navmesh input, so the spots beside it stay on the ground)
for i, x in enumerate((-30, -26, -22)):
    for j, y in enumerate((7.0, 11.5)):
        cyl(f'arbour_post{i}{j}', x, y, -0.2, 2.4, 0.07, 0.06, 7, M_WOOD, caster=True)
for j, y in enumerate((7.0, 11.5)):
    rod(f'arbour_beam{j}', (-30.2, y, 2.4), (-21.8, y, 2.4), 0.06, M_WOOD, caster=True)
for i in range(9):
    x = -30 + i
    rod(f'arbour_rafter{i}', (x, 6.8, 2.45), (x, 11.7, 2.45), 0.035, M_WOOD)
box('table', -26.6, -25.0, 8.8, 10.2, 0.72, 0.78, M_WOOD, group='far', tile=1.0)
for i, (x, y) in enumerate(((-26.4, 9.0), (-25.2, 9.0), (-26.4, 10.0), (-25.2, 10.0))):
    box(f'table_leg{i}', x - 0.04, x + 0.04, y - 0.04, y + 0.04, 0.0, 0.72, M_WOOD, group='far', tile=1.0)
box('bench_w', -27.5, -27.2, 8.6, 10.4, 0.42, 0.47, M_WOOD, group='far', tile=1.0)
box('bench_e', -24.4, -24.1, 8.6, 10.4, 0.42, 0.47, M_WOOD, group='far', tile=1.0)
for i, (x, y) in enumerate(((-27.35, 8.8), (-27.35, 10.2), (-24.25, 8.8), (-24.25, 10.2))):
    box(f'bench_leg{i}', x - 0.05, x + 0.05, y - 0.05, y + 0.05, 0.0, 0.42, M_WOOD, group='far', tile=1.0)
cyl('stump', -19.6, 9.4, 0.0, 0.42, 0.25, 0.24, 9, M_BARK, group='far')   # the groom's seat at his work (groom-work)

def arbour_leaves():
    """the vine over the arbour: leaf cards on the rafters, a broken roof of leaves with gaps of sky (no ripe grapes:
    early summer, village.md 2); the trunks climb the posts"""
    rr = random.Random(21)
    crowns = []
    for i in range(16):
        x = rr.uniform(-30, -22); y = rr.uniform(7, 11.5)
        crowns.append((Vector((x, y, 2.55)), rr.uniform(0.8, 1.2), 0.35))
    bl.leaf_cards('arbour_leaves', crowns, 10, 0.9, M_VINE, 'far', rr, depth=(0.2, 1.0))
    for i, x in enumerate((-30, -22)):
        rod(f'vine_trunk{i}', (x + 0.15, 7.15, 0), (x + 0.3, 7.6, 2.4), 0.05, M_BARK)
arbour_leaves()

# the threshing floor's kerb: a ring of low stones round the slabs, open where the path comes up
for k in range(30):
    a = 2 * math.pi * k / 30
    x, y = TH[0] + math.cos(a) * (TH_R + 0.1), TH[1] + math.sin(a) * (TH_R + 0.1)
    if abs(x - PATH[1][0]) < 1.1 and y > TH[1]:
        continue
    o = rock(f'kerb{k}', x, y, TH_Z + 0.05, 0.42, M_ROCK, squash=0.45, seed=500 + k, subdiv=1, caster=False)
    for f in o.data.polygons:
        f.use_smooth = True
# a few outcrops where the ground breaks through, off the paths
for i, (x, y, r) in enumerate(((-34, 14, 1.2), (-16, -6, 0.9), (34, 8, 1.3), (-34, -6, 1.0), (14.5, 21, 0.8))):
    rock(f'outcrop{i}', x, y, terrain(x, y) - 0.25 * r, r, M_ROCK, squash=0.55, seed=600 + i)


# ---------------------------------------------------------------- trees (village.md 2, 6.2: no prickly pear, no citrus)
fig = tree('fig', -11.5, -3.0, 5.5, 3.0, M_FIG, M_FIGBARK, 'round', z=terrain(-11.5, -3.0))
for i, (x, y, h) in enumerate(((-36, 5, 15), (-15, 16, 14), (38, -1, 15), (13, 26, 14))):
    tree(f'poplar{i}', x, y, h, 4.2, M_POPLAR, M_BARK, 'spread', z=terrain(x, y),
         lean=(random.uniform(-0.1, 0.1), random.uniform(-0.1, 0.1)))
for i, (x, y) in enumerate(((-17, -13), (36, 14), (-38, -20), (2, 24), (-6, 18))):
    tree(f'holmoak{i}', x, y, random.uniform(6, 8), 2.6, M_HOLM, M_BARK, 'round', z=terrain(x, y))


# ---------------------------------------------------------------- the instanced things (wheat, sheaves, vines, sheep)
def card_cluster(bm, uvl, rr, n, w, h, spread):
    """n crossed upright cards of the alpha-tested texture, base at z 0, standing within spread of the centre"""
    for k in range(n):
        x, y = rr.uniform(-spread, spread), rr.uniform(-spread, spread)
        a = rr.uniform(0, math.pi)
        dx, dy = math.cos(a) * w / 2, math.sin(a) * w / 2
        hh = h * rr.uniform(0.85, 1.1)
        lean = Vector((rr.uniform(-0.08, 0.08), rr.uniform(-0.08, 0.08), 0))
        vs = [bm.verts.new((x - dx, y - dy, 0)), bm.verts.new((x + dx, y + dy, 0)),
              bm.verts.new(Vector((x + dx, y + dy, hh)) + lean), bm.verts.new(Vector((x - dx, y - dy, hh)) + lean)]
        f = bm.faces.new(vs)
        u0 = rr.choice((0.0, 0.5))
        for l, uv in zip(f.loops, ((u0, 0), (u0 + 0.5, 0), (u0 + 0.5, 1), (u0, 1))):
            l[uvl].uv = uv

def proto(name, build, m):
    bm = bmesh.new()
    build(bm)
    bm.normal_update()
    o = bl.obj_from_bm(name, bm, [m], 'protos')
    o.hide_render = True
    return o

def up_normals(o):
    """cards lit as a mass (normals up and a little out), like the leaf cards"""
    o.data.normals_split_custom_set_from_vertices([Vector((0, 0, 1)) for _ in o.data.vertices])

P_WHEAT = proto('wheat', lambda bm: card_cluster(bm, bm.loops.layers.uv.new('UVMap'), random.Random(31), 7, 0.7, 1.0, 0.4), M_WHEAT)
up_normals(P_WHEAT)

def sheaf(bm):
    uvl = bm.loops.layers.uv.new('UVMap')
    seg = 8
    rings = [(0.0, 0.26), (0.35, 0.16), (0.55, 0.13), (1.05, 0.24), (1.25, 0.12)]
    vs = [[bm.verts.new((r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), z)) for i in range(seg)]
          for z, r in rings]
    for a, b in zip(vs, vs[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            f = bm.faces.new((a[i], a[j], b[j], b[i]))
            for l in f.loops:
                l[uvl].uv = (math.atan2(l.vert.co.y, l.vert.co.x) / math.pi, l.vert.co.z)
    f = bm.faces.new(vs[-1])
    for l in f.loops:
        l[uvl].uv = (l.vert.co.x, l.vert.co.y)
P_SHEAF = proto('sheaf', sheaf, M_SHEAF)
for f in P_SHEAF.data.polygons:
    f.use_smooth = True

def vine(bm):
    """a vine on its stake: the gnarled trunk, and a bush of leaf cards from knee height up"""
    uvl = bm.loops.layers.uv.new('UVMap')
    rr = random.Random(41)
    for k in range(10):
        c = Vector((rr.uniform(-0.35, 0.35), rr.uniform(-0.2, 0.2), rr.uniform(0.55, 1.35)))
        a = rr.uniform(0, 2 * math.pi)
        t = Vector((math.cos(a), math.sin(a), 0)) * 0.3
        b = Vector((0, 0, 0.3))
        vs = [bm.verts.new(c - t - b), bm.verts.new(c + t - b), bm.verts.new(c + t + b), bm.verts.new(c - t + b)]
        f = bm.faces.new(vs)
        u0, v0 = rr.random(), rr.random()
        for l, uv in zip(f.loops, ((u0, v0), (u0 + 0.38, v0), (u0 + 0.38, v0 + 0.38), (u0, v0 + 0.38))):
            l[uvl].uv = uv
P_VINE = proto('vine', vine, M_VINE)
up_normals(P_VINE)

def sheep(bm):
    """a placeholder sheep about 1.2 m long: a lumpy body, a head and four legs (sheep animation comes later)"""
    uvl = bm.loops.layers.uv.new('UVMap')
    g = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    for v in g['verts']:
        n = 1 + 0.07 * noise.noise(v.co * 3.0)
        v.co = Vector((v.co.x * 0.6 * n, v.co.y * 0.32 * n, 0.68 + v.co.z * 0.3 * n))
    h = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    for v in h['verts']:
        v.co = Vector((0.62 + v.co.x * 0.17, v.co.y * 0.1, 0.86 + v.co.z * 0.12 - 0.05 * v.co.x))
    for lx in (-0.35, 0.35):
        for ly in (-0.14, 0.14):
            c = bmesh.ops.create_cone(bm, segments=5, radius1=0.045, radius2=0.04, depth=0.5, cap_ends=False)
            for v in c['verts']:
                v.co += Vector((lx, ly, 0.25))
    for f in bm.faces:
        f.smooth = True
        for l in f.loops:
            l[uvl].uv = (l.vert.co.x, l.vert.co.z)
P_SHEEP = proto('sheep', sheep, M_WOOL)

INST = {}
def place(proto_o, x, y, rot, s, z=None):
    """a copy of the prototype at (x, y) on the ground, turned rot radians about up, scaled s; a linked duplicate in
    the 'inst' collection for the bake, and a row of <stem>_inst.json for merge_inst.mjs"""
    z = terrain(x, y) if z is None else z
    o = bpy.data.objects.new(f'{proto_o.name}.{len(INST.get(proto_o.name, []))}', proto_o.data)
    bl.coll('inst').objects.link(o)
    o.location = (x, y, z); o.rotation_euler = (0, 0, rot); o.scale = (s, s, s)
    INST.setdefault(proto_o.name, []).append([round(x, 3), round(y, 3), round(z, 3), round(rot, 4), round(s, 3)])

rr = random.Random(51)
def field(x0, x1, y0, y1, step=0.95):
    """standing wheat over a field, in rows a little off a grid, not over the field's edge"""
    y = y0 + 0.5
    while y < y1 - 0.4:
        x = x0 + 0.5 + rr.uniform(0, 0.3)
        while x < x1 - 0.4:
            place(P_WHEAT, x + rr.uniform(-0.2, 0.2), y + rr.uniform(-0.2, 0.2), rr.uniform(0, 2 * math.pi), rr.uniform(0.9, 1.1))
            x += step
        y += step
field(FIELD_SE[0], FIELD_SE[1], FIELD_SE[2], CUT_Y)
field(*FIELD_SW)
# the reaped part: sheaves stood up in pairs and threes across the stubble, the reapers' work this morning
for k in range(26):
    x, y = rr.uniform(15.5, 34.5), rr.uniform(CUT_Y + 0.8, -4.0)
    place(P_SHEAF, x, y, rr.uniform(0, 2 * math.pi), rr.uniform(0.9, 1.1))
    if rr.random() < 0.6:
        a = rr.uniform(0, 2 * math.pi)
        place(P_SHEAF, x + 0.5 * math.cos(a), y + 0.5 * math.sin(a), rr.uniform(0, 2 * math.pi), rr.uniform(0.85, 1.0))
# the vineyard north of the groom's house: rows east-west (village.md 2)
for j, y in enumerate((19.6, 21.1, 22.6, 24.1, 25.6)):
    x = -33.4 + 0.3 * (j % 2)
    while x < -16.5:
        place(P_VINE, x, y + rr.uniform(-0.08, 0.08), rr.uniform(-0.3, 0.3) + (math.pi if rr.random() < 0.5 else 0), rr.uniform(0.85, 1.05))
        x += 1.2
# the flock in the pasture round the sister (sister-sheep (16, 13)), grazing, loosely grouped; 20 head (village.md 6.1)
for k in range(20):
    a = rr.uniform(0, 2 * math.pi); d = rr.uniform(1.5, 8.0)
    x = min(30.5, max(7.5, 18 + math.cos(a) * d * 1.3)); y = min(22.5, max(5.0, 14 + math.sin(a) * d * 0.9))
    place(P_SHEEP, x, y, rr.uniform(0, 2 * math.pi), rr.uniform(0.85, 1.05))

json.dump({'note': 'build_village.py: plan x, y, z, rotation about up (rad), scale; merge_inst.mjs reads it',
           'instances': INST}, open(f'{OUT}/{STEM}_inst.json', 'w'), indent=0)
# the prototypes, each at the origin, as glTF (merge_inst.mjs makes the instanced nodes from them)
bpy.ops.object.select_all(action='DESELECT')
for o in bl.coll('protos').objects:
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=f'{OUT}/{STEM}_proto.glb', export_format='GLB', use_selection=True,
                          export_texcoords=True, export_normals=True, export_materials='EXPORT',
                          export_image_format='AUTO', export_apply=True, export_yup=True, export_extras=False)
bl.save(f'{OUT}/{STEM}_raw.blend')
