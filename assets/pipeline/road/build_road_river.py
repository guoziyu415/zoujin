# The road's river (F-10, ux/scenes/homeward-road.md 1): one source for both packs, RIVER_STATE picks the state.
#   calm  = act 2, 05:15: the wooden bridge whole, the river low and still, boats at the jetty, reeds on the west beach
#   flood = act 4, 11:45: bank-full brown water, the deck gone and the three pile pairs leaning or broken, the jetty
#           down to its stubs, the hut door open, fresh silt on the banks; the last 3 m of the west road under water
# Plan frame (homeward-road.md 0): +x = east (azimuth 90°), +y = north = upstream, z = 0 at the landings; the river
# runs south (-y). No rotation (layout rotationDeg 0), so the sun scripts get SCENE_MINUS_X_AZ = 270.
import bpy, os, sys, math, random   # bpy first: it brings mathutils
from mathutils import Vector, Matrix, noise
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import bl
from bl import box, cyl, rod, rock, tree, gable, heightfield, lines

STATE = os.environ['RIVER_STATE']
assert STATE in ('calm', 'flood'), STATE
FLOOD = STATE == 'flood'
OUT = os.environ['PLAZA_OUT']
STEM = os.environ['SCENE_STEM']
random.seed(7)
bl.setup(f'{OUT}/tex')
mat, pbr, tex_exists = bl.mat, bl.pbr, bl.tex_exists

# ---------------------------------------------------------------- materials (texture keys: ../common/road_tex.py)
M_ROAD = pbr('floor', 'road')       # named floor: the page's ambient ground colour reads materials.floor
M_GRAVEL = pbr('gravel', 'gravel')
M_GRASS = pbr('grass', 'grass')
M_ROCK = pbr('outcrop', 'outcrop')
M_BANK = pbr('bank', 'bank')
M_PEBBLE = pbr('pebbles', 'pebbles')
M_SILT = mat('silt', tex_exists('silt_base'), tex_exists('bank_nrm'), None, rough=0.55)
M_WOOD = pbr('wood', 'wood')
M_FRESH = mat('woodfresh', color=(0.62, 0.5, 0.34), rough=0.8)   # a fresh break: pale, untextured
M_THATCH = mat('thatch', tex_exists('thatch_base'), None, None, rough=0.95)
M_BARK = mat('bark', tex_exists('bark_base'), tex_exists('wood_nrm'), None, rough=0.9)
M_POPLAR = mat('poplar', tex_exists('poplar_base'), None, None, rough=0.8)
M_WILLOW = mat('willow', tex_exists('willow_base'), None, None, rough=0.8)
M_STRAND = mat('willowstrand', tex_exists('willowstrand_base'), None, None, rough=0.8)   # not baked (far)
M_HOLM = mat('holmoak', tex_exists('holmoak_base'), None, None, rough=0.85)
M_REED = mat('reed', tex_exists('reed_base'), None, None, rough=0.8)
M_HILL = mat('hill', tex_exists('hill_base'), tex_exists('outcrop_nrm'), None, rough=0.95)
M_WATER = mat('water', color=(0.16, 0.12, 0.07) if FLOOD else (0.04, 0.06, 0.06), rough=0.08)   # the page's shader replaces it
M_CLOUD = mat('raincloud', color=(0.13, 0.14, 0.16), rough=1.0)

WATER = -0.25 if FLOOD else -2.0    # layout.json water.levelM


# ---------------------------------------------------------------- the ground: one height function for near and far
def pl(x, pts):
    """piecewise linear through pts [(x, z)], flat beyond the ends"""
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
        if x <= x1:
            return z0 + (z1 - z0) * (x - x0) / (x1 - x0)
    return pts[-1][1]

def ss(x, a, b):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)

# across the river at the bridge: the west road dips 0.4 m to the bank (x = -5), a steep 1.4 m drop to the low west
# beach (reeds in act 2), the channel (bed -3.2, calm water -2.0, about 7.7 m wide), the low east beach where Melos
# washes, the bank up to the east landing (x = 11)
P_MAIN = [(-12, 0.0), (-5, -0.4), (-4.6, -1.2), (-4.2, -1.8), (-1.5, -1.85), (-0.6, -2.5), (0.5, -3.2), (5.4, -3.2),
          (6.2, -2.4), (6.5, -1.85), (8.0, -1.8), (10.6, -0.12), (11.2, -0.03), (12, 0.0)]
# the upstream shallows (y 9..16): wider (x -3..12) and shallower, a pebble bar in the middle (below)
P_SHALLOW = [(-12, 0.0), (-5, -0.4), (-4.5, -1.4), (-3.4, -2.1), (-2.4, -2.4), (10.4, -2.4), (11.4, -1.2),
             (12.0, -0.2), (12.6, -0.05), (13.5, 0.0)]
BREAKS_X = sorted({x for x, _ in P_MAIN + P_SHALLOW})

def w_shallows(y):
    return ss(y, 6.5, 9.0) * (1 - ss(y, 16.0, 18.5))

BAR_Y = (9.4, 15.8)
def bar(x, y):
    """the pebble bar (about x 3..7, y 10..15): drawn out along the flow, pointed at both ends, a ragged edge, crowned
    in the middle (top 15 cm above the calm water) and sliding under the water at its edges.
    Returns (weight, crown): how far to lift the bed, and 0..1 across the bar"""
    t = (y - BAR_Y[0]) / (BAR_Y[1] - BAR_Y[0])
    if not 0 < t < 1:
        return 0.0, 0.0
    half = 2.1 * math.sin(math.pi * t) ** 0.8 * (1 + 0.18 * noise.noise(Vector((y / 1.7, 0.3, 3.3))))
    dx = abs(x - (5.0 + 0.5 * math.sin(t * 2.4)))
    if dx >= half:
        return 0.0, 0.0
    return ss(half - dx, 0.0, 0.9), 1 - (dx / half) ** 2

def wiggle(y):
    """away from the bridge, the jetty and the shallows the channel wanders a little, so it never reads as a canal"""
    return ss(abs(y), 18, 26) * (1.5 * math.sin(y / 11) + 0.7 * math.sin(y / 5.3 + 1))

def terrain(x, y):
    x -= wiggle(y)
    w = w_shallows(y)
    z = pl(x, P_MAIN) * (1 - w) + pl(x, P_SHALLOW) * w
    b, crown = bar(x, y)
    top = -2.05 + 0.2 * crown
    if b > 0 and z < top:
        z += (top - z) * b
    # off the road and away from the banks the grass rolls a little; the road east climbs towards the pass
    land = 1 - ss(x, -13.0, -11.5) * (1 - ss(x, 12.5, 14.0))
    z += 0.18 * noise.noise(Vector((x / 7, y / 7, 0.4))) * ss(abs(y), 2.0, 5.0) * land
    z += max(0.0, x - 13.5) * 0.03
    return z

def meander(y):
    """beyond the near ground the river bends away: east going upstream, west going down (plan metres)"""
    return math.copysign(1, y) * 32 * ss(abs(y), 40, 170) ** 2

def valley(x, y):
    """the hills keep off the river valley (it runs north-south, bending away) until, at both ends, the valley turns
    in among them: no open horizon up or down the river"""
    return max(ss(abs(x - 3 - meander(y)), 30, 150), ss(abs(y), 150, 250))

def ridge_tan(ang):
    """tan of the horizon's elevation seen from the bridge, by plan angle (0 = east, 90° = north).
    East: the ridge at about 7° (layout ridgeElevationDeg) with the notch where the road goes up to the pass;
    north (upstream): higher mountains, rain clouds on them in act 4; west and south: low hills, the valley opens."""
    a = math.degrees(ang) % 360
    def bump(c, wdt):
        d = abs((a - c + 180) % 360 - 180)
        return max(0.0, math.cos(min(math.pi, d / wdt * math.pi / 2))) if d < wdt else 0.0
    e = 3.0 + 3.8 * bump(10, 70) + 9.0 * bump(95, 45) + 1.0 * bump(200, 60) - 1.0 * bump(270, 50)
    e -= 2.6 * bump(0, 9)      # the notch (the road to the pass)
    # a ragged skyline (peaks and saddles) everywhere but on the east ridge, whose 7° the page's sun test uses
    r = math.radians(a)
    rag = noise.noise(Vector((math.cos(r) * 2.2, math.sin(r) * 2.2, 7.7))) + 0.5 * noise.noise(Vector((math.cos(r) * 6, math.sin(r) * 6, 3.1)))
    e *= 1 + 0.32 * rag * (1 - bump(15, 65))
    return math.tan(math.radians(e))

def road_y(x):
    """the road beyond the near ground follows the land: west of about 45 m it swings south and out of sight behind
    the low hills; east it climbs in loose bends towards the notch (the pass), never in a ruled line"""
    if x < -40:
        return -0.012 * (x + 40) ** 2
    if x > 40:
        return 9 * ss(x, 40, 110) * math.sin((x - 40) / 28) - 4 * ss(x, 120, 220)
    return 0.0

def far_height(x, y):
    d = math.hypot(x, y)
    h = terrain(x - meander(y), y)
    if d > 40:
        n = noise.noise(Vector((x / 60, y / 60, 2.2))) * 0.5 + 0.5
        n2 = noise.noise(Vector((x / 17, y / 17, 5.1)))   # spurs and gullies on the slopes
        # peaks and saddles on the far skyline (60 m and up, the far grid's 30 m), not on the east ridge (the sun test)
        de = abs((math.degrees(math.atan2(y, x)) - 15 + 180) % 360 - 180)
        east = math.cos(de / 65 * math.pi / 2) if de < 65 else 0.0
        n3 = noise.noise(Vector((x / 45, y / 45, 9.1))) * ss(d, 180, 300) * (1 - east)
        hill = d * ridge_tan(math.atan2(y, x)) * ss(d, 90, 260) * (0.82 + 0.25 * n + 0.08 * n2 + 0.45 * n3)
        road = 1 - 0.5 * (1 - ss(abs(y - road_y(x)), 4, 16)) * ss(x, 40, 80)   # the road east keeps a shallow cut
        h += hill * valley(x, y) * road
    return h

ROAD_Y = 1.5      # the road is 3 m wide, gravel verges to 1.6 (homeward-road.md 0.4)

def ground_mat(cx, cy, cz):
    if cz < -0.45:
        return 4 if -2.0 < cz < -1.7 else 3   # the low beaches and the bar: pebbles; the rest of the channel: bank
    if FLOOD and -0.32 < cz < -0.04 and (cx < -6 or cx > 9) and abs(cy) > 1.1:
        return 5      # fresh silt along the flood line, off the road: the road runs on into the water
    if abs(cy) < 1.1 and not (-5 < cx < 11):
        return 0
    if abs(cy) < 1.6 and not (-5 < cx < 11):
        return 1
    return 2

GMATS = [M_ROAD, M_GRAVEL, M_GRASS, M_BANK, M_PEBBLE, M_SILT]
XS = lines((-40, -14, 2.0), (-14, -6, 1.0), (-6, 12, 0.5), (12, 14, 1.0), (14, 40, 2.0), extra=BREAKS_X)
YS = lines((-40, -20, 4.0), (-20, 9, 1.0), (9, 16, 0.5), (16, 20, 1.0), (20, 40, 4.0),
           extra=(-1.6, -1.1, 1.1, 1.6, 6.5, 18.5))
heightfield('ground', XS, YS, terrain, ground_mat, GMATS, 'ground', tile=3.0)

def far_mat(cx, cy, cz):
    if cz < -0.45:
        return 2
    return 3 if cz > 2.5 else 1

FX = lines((-340, -100, 30.0), (-100, 100, 12.0), (100, 340, 30.0), extra=[x for x in BREAKS_X] + [-40, 40])
FY = lines((-340, -100, 30.0), (-100, 100, 12.0), (100, 340, 30.0), extra=(-40, 40))
heightfield('far_land', FX, FY, far_height, far_mat, [M_ROAD, M_GRASS, M_BANK, M_HILL], 'far',
            skip=lambda cx, cy: abs(cx) < 40 and abs(cy) < 40, tile=12.0, tris=True)

def far_road():
    """the road past the near ground, a 3 m ribbon laid 12 cm over the far land's triangles along road_y (far group: not
    baked)"""
    import bmesh
    bm = bmesh.new()
    for xs in (lines((-150, -40, 3.0)), lines((40, 240, 3.0))):
        prev = None
        for x in xs:
            y = road_y(x)
            dx = 0.01
            t = Vector((dx, road_y(x + dx) - y, 0)).normalized()
            n = Vector((-t.y, t.x, 0)) * 1.5
            pair = [bm.verts.new((x + n.x * k, y + n.y * k, bl.grid_height(FX, FY, far_height, x + n.x * k, y + n.y * k) + 0.12)) for k in (-1, 1)]
            if prev:
                bm.faces.new((prev[0], pair[0], pair[1], prev[1]))
            prev = pair
    bm.normal_update()
    bl.box_uv_bm(bm, 3.0)
    bl.obj_from_bm('far_road', bm, [M_ROAD], 'far')
far_road()

# ---------------------------------------------------------------- water (its own node: the page's shader)
def water():
    xs = lines((-11.5, 15.5, 1.0)) if FLOOD else lines((-4.5, 9.5, 1.4))
    ys = lines((-240, -45, 15.0), (-45, 45, 1.0 if FLOOD else 3.0), (45, 240, 15.0))   # runs in under the closing hills
    o = heightfield('water', xs, ys, lambda x, y: WATER, lambda *a: 0, [M_WATER], 'dyn', tile=4.0)
    for v in o.data.vertices:   # follow the bends
        v.co.x += meander(v.co.y)
    o['caster'] = 0
water()

# ---------------------------------------------------------------- the bridge (homeward-road.md 1.1: three pile pairs)
PILES = (-1.0, 3.0, 7.0)
PILE_Y, PILE_TOP = 1.27, 1.05   # outside the 2.2 m deck; the tops stand 1 m over it
def bridge():
    # stone abutments both sides
    box('abut_w', -5.7, -4.5, -1.5, 1.5, -2.2, -0.42, M_ROCK, tile=1.5, caster=True)
    box('abut_e', 10.0, 11.3, -1.5, 1.5, -2.0, -0.08, M_ROCK, tile=1.5, caster=True)
    if not FLOOD:
        # deck: a ramp off the low west bank (x -5, z -0.4) up to the level deck at x -2, which runs to the east bank
        bm_ramp = Matrix.Translation((-5.0, 0, -0.4)) @ Matrix.Rotation(-math.atan2(0.4, 3.0), 4, 'Y')
        box('deck_ramp', 0, math.hypot(3.0, 0.4), -1.1, 1.1, -0.14, 0, M_WOOD, tile=1.2, caster=True, bottom=True,
            xform=bm_ramp)
        box('deck', -2.02, 11.1, -1.1, 1.1, -0.14, 0, M_WOOD, tile=1.2, caster=True, bottom=True)
        for i, x in enumerate(PILES):
            box(f'beam{i}', x - 0.12, x + 0.12, -1.42, 1.42, -0.42, -0.14, M_WOOD, tile=1.0, caster=True, bottom=True)
            for s in (-1, 1):   # each pile pair clasps its beam outside the deck and stands up as a big post
                cyl(f'pile{i}{s}', x, PILE_Y * s, -3.4, PILE_TOP, 0.15, 0.14, 10, M_WOOD, caster=True)
        # railings: posts every 1.6 m and a rail at 0.95 m
        for s in (-1, 1):
            yy = 1.02 * s
            k = 0
            for x in [-4.4 + 1.6 * i for i in range(10)]:
                z0 = -0.4 + 0.4 * (x + 5) / 3 if x < -2 else 0.0
                cyl(f'rail_post{s}{k}', x, yy, z0, z0 + 1.0, 0.05, 0.045, 6, M_WOOD, caster=True)
                k += 1
            rod(f'rail_w{s}', (-4.4, yy, -0.4 + 0.4 * 0.6 / 3 + 0.95), (-2.0, yy, 0.95), 0.04, M_WOOD, caster=True)
            rod(f'rail{s}', (-2.0, yy, 0.95), (10.0, yy, 0.95), 0.04, M_WOOD, caster=True)
    else:
        # the deck is gone; the pile pairs stand as UX 1.1 lists them
        tilt = Matrix.Translation((-1.0, 0, -3.4)) @ Matrix.Rotation(math.radians(16), 4, 'X') @ Matrix.Translation((1.0, 0, 3.4))
        for s in (-1, 1):   # x = -1: whole but leaning downstream, a beam end still pinned to one
            cyl(f'pile0{s}', -1.0, PILE_Y * s, -3.4, PILE_TOP, 0.15, 0.14, 10, M_WOOD, caster=True, xform=tilt)
        box('beam0', -1.12, -0.88, -0.3, 1.42, -0.05, 0.2, M_WOOD, tile=1.0, caster=True, bottom=True, xform=tilt)
        for s in (-1, 1):   # x = 3: snapped just above the water
            cyl(f'pile1{s}', 3.0, PILE_Y * s, -3.4, WATER + 0.12 + 0.05 * s, 0.15, 0.14, 10, M_WOOD, caster=True, cap_mat=M_FRESH)
        for s in (-1, 1):   # x = 7: 30 cm out of the water, branches caught on them
            cyl(f'pile2{s}', 7.0, PILE_Y * s, -3.4, WATER + 0.3, 0.15, 0.14, 10, M_WOOD, caster=True, cap_mat=M_FRESH)
        for i, (a, b) in enumerate([((5.6, 1.6, -0.2), (8.1, -0.5, -0.05)), ((6.2, 2.2, -0.15), (7.4, -1.6, -0.12)),
                                    ((6.8, 1.2, -0.08), (8.6, 0.6, -0.2))]):
            rod(f'snag{i}', a, b, 0.07 - 0.015 * i, M_BARK, caster=True)
        # the west end of the ramp still sits on its abutment, broken off
        box('deck_stub', -5.0, -4.2, -1.1, 1.1, -0.54, -0.4, M_WOOD, tile=1.2, caster=True, bottom=True)
        box('deck_stub_e', 10.3, 11.1, -1.1, 1.1, -0.14, 0, M_WOOD, tile=1.2, caster=True, bottom=True)
bridge()

# ---------------------------------------------------------------- jetty, boats, hut (south of the bridge, west bank)
JY = -10.0
def jetty():
    for i, x in enumerate((-4.0, -2.5, -1.2)):
        for s in (-1, 1):
            top = -1.25 if not FLOOD else (WATER + 0.1 + 0.08 * ((i + s) % 3))
            cyl(f'jetty_post{i}{s}', x, JY + 0.55 * s, -3.0, top, 0.1, 0.09, 8, M_WOOD, caster=True,
                cap_mat=M_FRESH if FLOOD else None)
    for i, (y0, y1) in enumerate(((-9.0, -8.6), (-11.6, -11.2))):   # two mooring posts on the bank
        cyl(f'mooring{i}', -5.5, (y0 + y1) / 2, -0.8, 0.55, 0.12, 0.1, 8, M_WOOD, caster=True)
    if not FLOOD:
        box('jetty_deck', -3.9, -1.0, JY - 0.6, JY + 0.6, -1.25, -1.13, M_WOOD, tile=1.2, caster=True, bottom=True)
        ramp = Matrix.Translation((-5.0, 0, -0.4)) @ Matrix.Rotation(-math.atan2(0.73, 1.1), 4, 'Y')
        box('jetty_ramp', 0, math.hypot(1.1, 0.73), JY - 0.6, JY + 0.6, -0.12, 0, M_WOOD, tile=1.2, caster=True,
            bottom=True, xform=ramp)
        for i, (bx, by) in enumerate(((-2.4, JY - 1.25), (-2.1, JY + 1.25))):
            boat(f'boat{i}', bx, by)
            rod(f'boat_rope{i}', (-5.5, by + (0.4 if by > JY else -0.4), 0.45), (bx - 1.7, by, WATER + 0.35), 0.015, M_BARK)
    else:
        for i, s in enumerate((1, -1)):   # rope ends torn off the posts, hanging
            y = -8.8 if s > 0 else -11.4
            rod(f'rope_end{i}', (-5.38, y, 0.4), (-5.2, y + 0.05, -0.1), 0.018, M_BARK)

def boat(name, cx, cy, L=3.6, W=1.1, D=0.5):
    """a plank boat moored along x: a hull lofted over five sections, pointed at both ends"""
    import bmesh
    bm = bmesh.new()
    secs = []
    for t in (-1.0, -0.6, 0.0, 0.6, 1.0):
        w = W / 2 * (1 - t * t) ** 0.6 if abs(t) < 1 else 0.02
        z0 = WATER - D * (1 - 0.6 * t * t) + 0.25
        x = cx + t * L / 2
        ring = lambda i: [(x, cy - w + i, WATER + 0.3), (x, cy - w * 0.7 + i, z0 + i), (x, cy + w * 0.7 - i, z0 + i),
                          (x, cy + w - i, WATER + 0.3)]
        secs.append(([bm.verts.new(v) for v in ring(0)], [bm.verts.new(v) for v in ring(0.03 if abs(t) < 1 else 0)]))
    for (a, ai), (b, bi) in zip(secs, secs[1:]):
        for k in range(3):
            bm.faces.new((a[k], b[k], b[k + 1], a[k + 1]))
            bm.faces.new((ai[k + 1], bi[k + 1], bi[k], ai[k]))   # the inside: the boats are open
    bm.normal_update(); bl.box_uv_bm(bm, 1.2)
    bl.obj_from_bm(name, bm, [M_WOOD], 'arch', True)

HUT = (-12.5, -9.5, -13.5, -10.5)   # the ferryman's hut, 3 × 3 m, door on the east (river) side
def hut():
    x0, x1, y0, y1 = HUT
    t, h = 0.4, 2.2
    z0 = terrain((x0 + x1) / 2, (y0 + y1) / 2) - 0.3
    box('hut_w', x0, x0 + t, y0, y1, z0, h, M_ROCK, tile=2.0, caster=True)
    box('hut_s', x0, x1, y0, y0 + t, z0, h, M_ROCK, tile=2.0, caster=True)
    box('hut_n', x0, x1, y1 - t, y1, z0, h, M_ROCK, tile=2.0, caster=True)
    dy0, dy1 = -12.45, -11.55   # the door, 0.9 m wide, 1.8 m high
    box('hut_e1', x1 - t, x1, y0 + t, dy0, z0, h, M_ROCK, tile=2.0, caster=True)
    box('hut_e2', x1 - t, x1, dy1, y1 - t, z0, h, M_ROCK, tile=2.0, caster=True)
    box('hut_lintel', x1 - t, x1, dy0, dy1, 1.8, h, M_ROCK, tile=2.0, caster=True, bottom=True)
    hinge = Vector((x1 - 0.05, dy0, 0))
    yaw = Matrix.Translation(hinge) @ Matrix.Rotation(math.radians(-75 if FLOOD else 0), 4, 'Z') @ Matrix.Translation(-hinge)
    box('hut_door', x1 - 0.1, x1 - 0.04, dy0 + 0.02, dy1 - 0.02, 0.0, 1.78, M_WOOD, tile=1.0, caster=True, xform=yaw)
    gable('hut', x0, x1, y0, y1, h, M_THATCH, M_ROCK, pitch_deg=38, over=0.4)
    box('hut_floor', x0 + t, x1 - t, y0 + t, y1 - t, z0, terrain(x1, dy0) + 0.04, M_ROCK, tile=1.5)
jetty()
hut()

# ---------------------------------------------------------------- trees, rocks, walls, reeds (homeward-road.md 1.1, 0.4)
# white poplars: broad ragged crowns about 15 m up, a head above the holm oaks, trunks often leaning
for i, (x, y) in enumerate(((-8, 7), (-9, 13), (-7, -17), (13, 5), (14.2, 11), (14.5, -21.5))):   # not behind the willow seen from road-west
    tree(f'poplar{i}', x, y, random.uniform(14, 16), 4.5, M_POPLAR, M_BARK, 'spread', z=terrain(x, y),
         lean=(random.uniform(-0.12, 0.12), random.uniform(-0.12, 0.12)))
# the willow on the east bank (swim-out: beat.18, Melos gets hold of its trunk in the flood): about 10 m, one trunk
# leaning about 30° out over the water from its roots and a little downstream, so from road-west it is seen side-on;
# the crown hangs over the river, its roots bared by the water (UX on #103, a713399)
WX, WY = 11.8, -11.6
WLEAN = Vector((-0.6, -0.8, 0.0)).normalized()
def willow():
    import bmesh
    z0 = terrain(WX, WY)
    def along(p, ang, length):   # from p, length metres at ang degrees from the vertical, towards WLEAN
        a = math.radians(ang)
        return p + WLEAN * math.sin(a) * length + Vector((0, 0, math.cos(a) * length))
    p0 = Vector((WX, WY, z0 - 0.3))
    p1 = along(p0, 28, 3.6)
    p2 = along(p1, 38, 3.0)
    rod('willow_trunk', p0, p1, 0.3, M_BARK, caster=True)
    rod('willow_trunk2', p1 - WLEAN * 0.05, p2, 0.24, M_BARK, caster=True)
    side = Vector((-WLEAN.y, WLEAN.x, 0))
    tips = []
    for i, (s_, out, up) in enumerate(((-1.0, 1.4, 1.6), (0.0, 2.2, 1.2), (1.0, 1.5, 1.7), (0.4, -0.6, 2.0))):
        t = p2 + side * s_ * 1.6 + WLEAN * out + Vector((0, 0, up))
        rod(f'willow_limb{i}', p2, t, 0.11, M_BARK, caster=True)
        tips.append(t)
    # the crown: drooping blobs round the limb tips, their lower halves pulled down into a curtain over the water
    bm = bmesh.new()
    rr = random.Random(11)
    crowns = []
    for i, c in enumerate(tips + [p2 + Vector((0, 0, 1.4)) + WLEAN * 0.6]):
        rad = rr.uniform(1.3, 1.7)
        crowns.append((c.copy(), rad, 1.25))
        g = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rad)
        for v in g['verts']:
            n = noise.noise(v.co * 1.7 + Vector((WX, WY, i))) * 0.3
            v.co = Vector((c.x + v.co.x * (1 + n), c.y + v.co.y * (1 + n), c.z + v.co.z * 1.25 * (1 + n)))
    top = p2.z + 1.0
    for v in bm.verts:
        if v.co.z < top:
            d = Vector((v.co.x - p2.x, v.co.y - p2.y, 0))
            v.co += d * 0.12 + Vector((0, 0, -(top - v.co.z) * 0.55))
    for f in bm.faces:
        f.smooth = True
    bm.normal_update()
    bl.box_uv_bm(bm, 1.6)
    bl.obj_from_bm('willow_leaves', bm, [M_WILLOW], 'arch', True)
    bl.leaf_cards('willow_cards', crowns, 14, 1.0, M_WILLOW, 'far', random.Random(12), droop=True)
    # hanging strands below the crown (not baked like the reeds): the willow's falling branches, cards 0.3 m wide of
    # the alpha-tested strand texture (twigs with narrow leaves; the page draws both sides), facing out of the crown,
    # down to about a metre over the flood
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    for k in range(80):
        c = tips[k % len(tips)]
        a = rr.uniform(0, 2 * math.pi); d = rr.uniform(0.6, 2.2)
        x, y = c.x + math.cos(a) * d, c.y + math.sin(a) * d
        zt = c.z - rr.uniform(0.4, 1.0)
        zb = max(WATER + 0.9, zt - rr.uniform(2.0, 3.6))
        b = a + math.pi / 2 + rr.uniform(-0.5, 0.5)
        dx, dy = math.cos(b) * 0.15, math.sin(b) * 0.15
        sw = Vector((rr.uniform(-0.15, 0.15), rr.uniform(-0.15, 0.15), 0))
        vs = [bm.verts.new(Vector((x - dx, y - dy, zb)) + sw), bm.verts.new(Vector((x + dx, y + dy, zb)) + sw),
              bm.verts.new((x + dx, y + dy, zt)), bm.verts.new((x - dx, y - dy, zt))]
        f = bm.faces.new(vs)
        for l, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):   # the texture's top (the twig's start) up
            l[uvl].uv = uv
    bm.normal_update()
    bl.obj_from_bm('willow_strands', bm, [M_STRAND], 'far')
    # the roots the river has bared: out of the foot of the trunk, arching over the bank edge into the water
    for i, a in enumerate((-75, -40, -12, 15, 45, 80)):
        r = math.atan2(WLEAN.y, WLEAN.x) + math.radians(a)
        L = 1.3 + 0.5 * math.cos(math.radians(a))
        ex, ey = WX + math.cos(r) * L, WY + math.sin(r) * L
        mid = Vector(((WX + ex) / 2, (WY + ey) / 2, max(terrain(WX, WY), terrain(ex, ey)) + 0.18))
        rod(f'willow_root{i}a', (WX, WY, z0 + 0.35), mid, 0.11, M_BARK, caster=True)
        rod(f'willow_root{i}b', mid, (ex, ey, terrain(ex, ey) - 0.2), 0.08, M_BARK, caster=True)
willow()
for i, (x, y) in enumerate(((28, 12), (-30, 9), (31, -10))):
    tree(f'holmoak{i}', x, y, random.uniform(6, 8), 2.6, M_HOLM, M_BARK, 'round', z=terrain(x, y))
for i, (x, y, r) in enumerate(((-9.5, -5.5, 1.3), (14.5, -8.0, 1.6), (-13.5, 9.5, 1.1), (16.5, 13.0, 1.8),
                               (-6.2, -14.5, 0.9), (12.0, 17.5, 1.2))):
    rock(f'outcrop{i}', x, y, terrain(x, y) - 0.25 * r, r, M_ROCK, squash=0.55, seed=i)
# the upstream shallows (aff.river-shallows, 「流れの緩い浅瀬を探す」): four big round boulders on the pebble bar in a
# line slanting across the river (from the east bank upstream to the west: seen broadside from the bridgehead), their tops 0.2〜0.4 m over the flood (UX on #103, a713399); in act 2 they stand on
# the bar. Each is stretched from 0.3 m into the bed up to its top
for i, (x, y, top, r) in enumerate(((7.2, 10.6, 0.05, 0.95), (5.9, 11.8, 0.12, 1.05), (4.6, 13.0, -0.02, 0.9),
                                    (3.3, 14.2, 0.1, 1.0))):
    o = rock(f'boulder{i}', x, y, 0.0, r, M_ROCK, squash=1.0, seed=20 + i)
    zs = [v.co.z for v in o.data.vertices]
    lo, hi, bed = min(zs), max(zs), terrain(x, y) - 0.3
    for v in o.data.vertices:
        v.co.z = bed + (v.co.z - lo) / (hi - lo) * (top - bed)
def flood_bar():
    """act 4: in the lee of the boulders the flood has thrown up a gravel spit, its crown a little over the water, and
    stones lie round it and the boulders, some just awash (UX round 2 ⑥: the shallows must read as shallows). Their feet
    end under the opaque water, not on the bed far below"""
    rr = random.Random(31)
    for i, (x, y, rx, ry, top) in enumerate(((5.9, 9.2, 1.5, 3.4, 0.16), (3.0, 12.2, 1.0, 2.0, 0.09))):
        o = rock(f'gravelbar{i}', x, y, 0.0, 1.0, M_PEBBLE, squash=0.5, seed=40 + i, caster=False)
        zs = [v.co.z for v in o.data.vertices]
        lo, hi = min(zs), max(zs)
        for v in o.data.vertices:
            v.co.x = x + (v.co.x - x) * rx
            v.co.y = y + (v.co.y - y) * ry / 0.8
            v.co.z = -0.7 + (v.co.z - lo) / (hi - lo) * (top + 0.7)
    for i in range(12):
        a = rr.uniform(0, 2 * math.pi)
        cx, cy = (5.9, 9.4) if i < 7 else (5.2, 12.4)
        d = rr.uniform(1.0, 2.6)
        x, y = cx + math.cos(a) * d * 0.7, cy + math.sin(a) * d
        r = rr.uniform(0.18, 0.4)
        top = rr.uniform(-0.04, 0.18)
        o = rock(f'stone{i}', x, y, 0.0, r, M_ROCK, squash=0.7, seed=60 + i, caster=False, subdiv=1)   # small: coarse
        zs = [v.co.z for v in o.data.vertices]
        lo, hi = min(zs), max(zs)
        for v in o.data.vertices:
            v.co.z = -0.7 + (v.co.z - lo) / (hi - lo) * (top + 0.7)
if FLOOD:
    flood_bar()
# dry-stone walls along the road, off the landings (nothing but road and low grass 9 m behind them): two courses of
# rough stones, each its own lump, the top ragged (UX round 3 ⑦: a box read as a concrete beam)
def drystone(name, x0, x1, y, seed):
    rr = random.Random(seed)
    for c, (zc, hc) in enumerate(((0.2, 0.42), (0.58, 0.34))):
        x = x0 + (0.0 if c == 0 else rr.uniform(0.2, 0.4))
        k = 0
        while x < x1 - 0.2:
            L = min(rr.uniform(0.5, 0.85), x1 - x)
            g = terrain(x + L / 2, y)
            o = rock(f'{name}_{c}_{k}', x + L / 2, y + rr.uniform(-0.05, 0.05), 0.0, 1.0, M_ROCK, squash=1.0,
                     seed=seed * 10 + c * 50 + k, subdiv=1)
            zs = [v.co.z for v in o.data.vertices]
            xs = [v.co.x for v in o.data.vertices]
            ys = [v.co.y for v in o.data.vertices]
            lo, hi = min(zs), max(zs)
            top = g + zc + hc * rr.uniform(0.75, 1.1) - (0.1 if c == 0 else 0.0)
            for v in o.data.vertices:
                v.co.x = x + L / 2 + (v.co.x - (min(xs) + max(xs)) / 2) / (max(xs) - min(xs)) * L * 1.08
                v.co.y = y + (v.co.y - (min(ys) + max(ys)) / 2) / (max(ys) - min(ys)) * rr.uniform(0.5, 0.62)
                v.co.z = g - 0.25 + (v.co.z - lo) / (hi - lo) * (top - g + 0.25) if c == 0 else \
                    g + zc - 0.2 + (v.co.z - lo) / (hi - lo) * (top - g - zc + 0.2)
            for f in o.data.polygons:   # coarse, so smooth: faceted they read as crystals
                f.use_smooth = True
            x += L * rr.uniform(0.92, 1.0)
            k += 1
for i, (x0, x1, y) in enumerate(((-14.5, -8.5, -3.6), (-13.5, -9.0, 3.8), (13.0, 15.8, 3.6))):   # far-bank stands south of the east road
    drystone(f'wall{i}', x0, x1, y, 70 + i)

def reeds():
    """act 2 only: reed clumps on the west beach, crossed pairs of thin cards (far group: not baked)"""
    import bmesh
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    rr = random.Random(5)
    for k in range(70):
        y = rr.choice((rr.uniform(-8, -2.5), rr.uniform(2.5, 8)))
        x = rr.uniform(-4.0, -1.7)
        z = terrain(x, y) - 0.05
        h = rr.uniform(1.0, 1.6); w = rr.uniform(0.35, 0.6)
        for a in (rr.uniform(0, math.pi), None):
            a = a if a is not None else a_prev + math.pi / 2
            a_prev = a
            dx, dy = math.cos(a) * w / 2, math.sin(a) * w / 2
            lean = Vector((rr.uniform(-0.15, 0.15), rr.uniform(-0.15, 0.15), 0))
            vs = [bm.verts.new((x - dx, y - dy, z)), bm.verts.new((x + dx, y + dy, z)),
                  bm.verts.new(Vector((x + dx, y + dy, z + h)) + lean), bm.verts.new(Vector((x - dx, y - dy, z + h)) + lean)]
            f = bm.faces.new(vs)
            for l, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
                l[uvl].uv = uv
    bm.normal_update()
    bl.obj_from_bm('reeds', bm, [M_REED], 'far')
if not FLOOD:
    reeds()

def rain_clouds():
    """act 4: the dark rain cloud still sitting on the mountains upstream (north), a few layered cards whose lower edge
    follows the slopes below the skyline, so the cloud lies on the mountains, not above an empty horizon"""
    import bmesh
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    rr = random.Random(9)
    for k in range(4):
        d = 260 + 25 * k
        pts = []
        for i in range(49):
            a = math.radians(55 + 70 * i / 48)
            x, y = d * math.cos(a), d * math.sin(a)
            low = 0.7 * far_height(x, y) + 4 * k
            # rounded billows (two slow swells and a little noise), not a saw-tooth that reads as more mountains
            top = low + 45 + 14 * math.sin(i * 0.3 + 1.7 * k) + 6 * math.sin(i * 0.7 + k) + 2 * rr.random()
            # both ends taper down onto the slopes (UX: no vertical cut at 55°)
            top = low + (top - low) * ss(i, 0, 12) * ss(48 - i, 0, 12)
            pts.append((x, y, low, top))
        for (x0, y0, b0, t0), (x1, y1, b1, t1) in zip(pts, pts[1:]):
            vs = [bm.verts.new((x1, y1, b1)), bm.verts.new((x0, y0, b0)), bm.verts.new((x0, y0, t0)), bm.verts.new((x1, y1, t1))]
            f = bm.faces.new(vs)
            for l, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
                l[uvl].uv = uv
    bm.normal_update()
    bl.obj_from_bm('raincloud', bm, [M_CLOUD], 'far')
if FLOOD:
    rain_clouds()

bl.save(f'{OUT}/{STEM}_raw.blend')
