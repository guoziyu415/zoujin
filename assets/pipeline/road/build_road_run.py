# The run segments (F-15, ux/scenes/homeward-road.md 4, 5): the "treadmill". Each pack is one stretch of roadside,
# TILE metres long, that joins onto itself end to end (the ground, the road and everything on it repeat with period
# TILE along x), so the page lays a few copies in a row and scrolls them back under the runners, who run on the spot.
# RUN picks the roadside:
#   r1     river -> pass (act 4, 12:10..13:40): the wet slope up out of the valley, olive terraces, dry-stone walls
#   r2     pass -> spring (14:05..14:55): the stony way down, scree, outcrops, dwarf fan palms, mastic, heat
#   r2s    the goat track round the shoulder (「峠を避けて、脇道を行く」): a narrow path through holm-oak scrub
#   r3     spring -> the field road (16:30..17:20): meadow, olive groves, cypresses far off, the first wheat
#   field  市へ続く野の道 (17:20..18:55): F1 wheat on both sides as the tile; set pieces (dyn nodes, shown by the clock):
#          F2 the harvest feast spread across the road, F3 the brook with stepping stones, F5 rock-cut tombs and
#          cypresses, F6 the city wall and the west gate, F1' the narrow path through the wheat; the city's far
#          silhouette (towers) that the page scales by the distance left
#   night  act 2's night road (02:45..05:10, walked the other way): a dry tile; set pieces for the stretch with the
#          spring (three planes and the rock, black against the stars) and the top of the pass (the two rocks of the
#          gate, low), so act 2 does not download the spring's or the pass's packs
# Nodes: ground, arch, proxy and tile_* scroll with the tiles; set_* are set pieces placed on a tile; far stays put.
# Plan frame: +x = the way the runners go (towards Syracuse in act 4; act 2's night road runs it backwards, so the
# page turns the runners round), the road on y = 0, z = 0 on the road. No rotation; SCENE_MINUS_X_AZ per run.
import bpy, os, sys, math, random   # bpy first: it brings mathutils
from mathutils import Vector, noise
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common')]
import bl
import roadkit as rk
from bl import box, rock, tree, heightfield, lines
from roadkit import pl, ss

RUN = os.environ['RUN']
assert RUN in ('r1', 'r2', 'r2s', 'r3', 'field', 'night'), RUN
OUT = os.environ['PLAZA_OUT']
STEM = os.environ['SCENE_STEM']
TILE = 36.0                 # layout.json runway.tileLengthM
HALF = TILE / 2
WIDE = 20.0                 # the tile's ground runs to |y| = 20; the far land starts there
ROAD_W = 0.5 if RUN == 'r2s' else 1.5
random.seed({'r1': 1, 'r2': 2, 'r2s': 3, 'r3': 4, 'field': 5, 'night': 6}[RUN])
bl.setup(f'{OUT}/tex')
M = rk.materials()
M_SCREE = bl.mat('scree', bl.tex_exists('gravel_base'), bl.tex_exists('outcrop_nrm'), None, rough=0.9)


def pnoise(x, y, s, seed):
    """noise that repeats every TILE along x: x goes round a circle"""
    a = 2 * math.pi * x / TILE
    R = TILE / (2 * math.pi * s)
    return noise.noise(Vector((math.cos(a) * R, math.sin(a) * R, y / s + seed)))


def wrap(x):
    """a plan x folded into the tile (things near one end are also drawn at the other, so nothing is cut)"""
    return (x + HALF) % TILE - HALF


# ---------------------------------------------------------------- the cross profile of each roadside (y -> z)
PROFILE = {
    'r1': [(-20, -3.0), (-8, -1.2), (-3, -0.2), (-ROAD_W, 0), (ROAD_W, 0), (4, 0.6), (8, 1.4), (12, 2.4), (20, 4.4)],
    'r2': [(-20, -5.0), (-6, -1.4), (-2.5, -0.15), (-ROAD_W, 0), (ROAD_W, 0), (3, 0.5), (8, 2.6), (20, 7.0)],
    'r2s': [(-20, -8.0), (-6, -3.2), (-1.0, -0.2), (-ROAD_W, 0), (ROAD_W, 0), (1.2, 0.4), (6, 3.2), (20, 10.0)],
    'r3': [(-20, -0.6), (-5, -0.15), (-2, 0.0), (2, 0.0), (5, 0.2), (20, 1.2)],
    'field': [(-20, -0.3), (-2.2, -0.05), (-ROAD_W, 0), (ROAD_W, 0), (2.2, -0.05), (20, -0.2)],
    'night': [(-20, -0.8), (-5, -0.2), (-2, 0.0), (2, 0.0), (5, 0.3), (20, 1.6)],
}[RUN]
ROUGH = {'r1': 0.25, 'r2': 0.4, 'r2s': 0.35, 'r3': 0.18, 'field': 0.08, 'night': 0.2}[RUN]

def terrain(x, y):
    z = pl(y, PROFILE)
    off = ss(abs(y), ROAD_W + 0.3, ROAD_W + 2.5)
    z += ROUGH * pnoise(x, y, 5.0, 1.3) * off + 0.5 * ROUGH * pnoise(x, y, 1.7, 7.1) * off
    if RUN == 'r1':   # olive terraces north of the road: a step every 4 m
        if y > 3:
            z = pl(y, PROFILE) - 0.45 * ss((y - 3) % 4, 0.0, 0.8) + 0.45
    return z

def ground_mat(cx, cy, cz):
    ay = abs(cy)
    if ay < ROAD_W - 0.05:
        return 0
    if ay < ROAD_W + 0.5:
        return 1
    if RUN in ('r2', 'r2s') and (ay > 3.5 or pnoise(cx, cy, 2.5, 4.0) > 0.25):
        return 3   # scree
    return 2

GMATS = [M['road'], M['gravel'], M['grass'], M_SCREE]
XS = lines((-HALF, HALF, 0.75))
YS = lines((-WIDE, -6, 1.5), (-6, 6, 0.5), (6, WIDE, 1.5), extra=(-ROAD_W, ROAD_W, -ROAD_W - 0.5, ROAD_W + 0.5))
heightfield('ground', XS, YS, terrain, ground_mat, GMATS, 'ground', tile=3.0)

# ---------------------------------------------------------------- the far land: static, round the strip the tiles cover
FAR = {   # which side climbs (plan angle of the high side, tangent), which falls away
    'r1': ((90, 0.16), (270, 0.06)), 'r2': ((90, 0.14), (270, 0.10)), 'r2s': ((90, 0.2), (270, 0.1)),
    'r3': ((150, 0.06), (0, 0.02)), 'field': ((90, 0.03), (0, 0.0)), 'night': ((90, 0.08), (0, 0.0)),
}[RUN]
def far_height(x, y):
    z = pl(y, PROFILE) - 0.3
    d = abs(y) - WIDE
    if d > 0:
        side = FAR[0] if y > 0 else FAR[1]
        n = noise.noise(Vector((x / 70, y / 70, 5.5))) * 0.5 + 0.5
        z += d * side[1] * (0.7 + 0.6 * n) * ss(d, 0, 120)
    return z

def far_mat(cx, cy, cz):
    if abs(cy) < 2:
        return 0
    if RUN == 'field' and abs(cy) < 160:
        return 3   # wheat-gold fields far off
    return 2 if cz > 5 else 1

FX = lines((-340, -100, 30.0), (-100, 100, 12.0), (100, 340, 30.0))
FY = lines((-340, -100, 30.0), (-100, -WIDE, 12.0), (WIDE, 100, 12.0), (100, 340, 30.0))
M_FARWHEAT = bl.mat('farwheat', bl.tex_exists('wheat_base'), None, None, rough=0.95)
heightfield('far_land', FX, FY, far_height, far_mat, [M['road'], M['grass'], M['hill'], M_FARWHEAT], 'far',
            skip=lambda cx, cy: abs(cy) < WIDE, tile=12.0, tris=True)

# ---------------------------------------------------------------- roadside, per run (positions folded into the tile)
rr = random.Random(77)

def scatter(n, ymin, ymax, both=True):
    out = []
    for _ in range(n):
        y = rr.uniform(ymin, ymax) * (rr.choice((-1, 1)) if both else 1)
        out.append((rr.uniform(-HALF + 1, HALF - 1), y))
    return out

def walls(y, gap=None):
    """a dry-stone wall along the road at y, the length of the tile (its ends meet the next tile's)"""
    z = terrain(0, y)
    if gap:
        box(f'wall_{y}a', -HALF, gap[0], y - 0.3, y + 0.3, z - 0.3, z + 0.8, M['rock'], tile=1.6, caster=True)
        box(f'wall_{y}b', gap[1], HALF, y - 0.3, y + 0.3, z - 0.3, z + 0.8, M['rock'], tile=1.6, caster=True)
    else:
        box(f'wall_{y}', -HALF, HALF, y - 0.3, y + 0.3, z - 0.3, z + 0.8, M['rock'], tile=1.6, caster=True)

def trees(kind, pts, h, r, m_leaf, shape='round'):
    for i, (x, y) in enumerate(pts):
        tree(f'{kind}{i}', x, y, rr.uniform(*h), r, m_leaf, M['bark'], shape, z=terrain(x, y))

def rocks(pts, rmin, rmax, squash=0.7):
    for i, (x, y) in enumerate(pts):
        rock(f'rock{i}', x, y, terrain(x, y) - 0.15, rr.uniform(rmin, rmax), M['rock'], squash=squash, seed=200 + i)

def palms(pts):
    for i, (x, y) in enumerate(pts):
        rk.palm(f'tile_palm{i}', x, y, terrain(x, y), rr.uniform(0.7, 1.1), M['palm'], seed=i, group='dyn')

# the default camera rides beside and behind the runners (homeward-road.md 5): keep 1.5 m either side of the road clear
CLEAR = ROAD_W + 1.5
if RUN == 'r1':
    for y in (7.0, 11.0, 15.0):
        walls(y)
    walls(-3.2, gap=(-4, 2))
    trees('olive', [(x, y) for x, y in ((-12, 5.2), (2, 5.4), (13, 9.2), (-5, 9.4), (8, 13.2), (-14, 13.4), (0, 17))],
          (4, 5.5), 2.3, M['holm'])
    trees('holm', [(-9, -7), (10, -9), (-1, -14)], (6, 8), 2.6, M['holm'])
    rocks(scatter(10, CLEAR + 1, 6), 0.3, 0.8)
elif RUN in ('r2', 'r2s'):
    rocks(scatter(14, CLEAR + 0.5, 16), 0.5, 1.6, squash=0.8)
    palms(scatter(18, CLEAR + 0.3, 14))
    for i, (x, y) in enumerate(scatter(12, CLEAR + 0.5, 12)):
        rk.shrub(f'bush{i}', x, y, terrain(x, y), rr.uniform(0.5, 0.9), M['holm'], M['bark'])
    if RUN == 'r2s':   # the holm-oak scrub closes round the track
        trees('scrub', scatter(14, CLEAR, 7), (3, 4.5), 1.8, M['holm'])
elif RUN in ('r3', 'night'):
    trees('olive', scatter(12, CLEAR + 2.5, 16), (4, 5.5), 2.4, M['holm'])
    rocks(scatter(5, CLEAR + 1, 10), 0.3, 0.7)
    walls(-3.0, gap=(5, 8))
    for i, (x, y) in enumerate(((-14, 18.5), (6, -18.5), (16, 17.5))):
        rk.cypress(f'tile_cypress{i}', x, y, terrain(x, y), rr.uniform(9, 12), M['cypress'], group='dyn')
    tuft = [(x, y, terrain(x, y)) for x, y in scatter(140, CLEAR, WIDE - 1)]
    rk.cards('tile_tufts', tuft, M['wheat'], h=(0.3, 0.55), w=(0.4, 0.6), seed=11, group='dyn')
    if RUN == 'r3':   # the wheat begins, on the left far side
        wheat = [(x + rr.uniform(-0.3, 0.3), y, terrain(x, y)) for x in range(-17, 18) for y in (-12.0, -13.2, -14.4, -15.6)]
        rk.cards('tile_wheat', wheat, M['wheat'], h=(0.8, 1.0), w=(0.9, 1.1), seed=12, group='dyn')
elif RUN == 'field':
    walls(-3.6, gap=(-2, 1))
    walls(3.6, gap=(9, 12))
    trees('olive', [(-9, 7.5), (12, -8.5), (2, 15)], (4, 5.5), 2.4, M['holm'])
    rows = [(x + rr.uniform(-0.25, 0.25), s * (4.4 + 1.1 * k)) for x in [i * 0.9 - HALF + 0.45 for i in range(40)]
            for s in (-1, 1) for k in range(10)]
    # part of the wheat already cut: a gap in the rows on the north side, sheaves standing in the stubble
    stand = [(x, y) for x, y in rows if not (y > 0 and -6 < x < 7)]
    rk.cards('tile_wheat', [(x, y, terrain(x, y)) for x, y in stand], M['wheat'], h=(0.85, 1.05), w=(0.95, 1.15), seed=13,
             group='dyn')
    for i, (x, y) in enumerate(((-4, 6), (-1, 8.5), (2.5, 6.5), (5, 9))):
        rk.cards(f'tile_sheaf{i}', [(x, y, terrain(x, y))], M['wheat'], h=(1.0, 1.1), w=(0.5, 0.6), seed=20 + i, group='dyn')

# ---------------------------------------------------------------- set pieces (dyn, one node each, placed on a tile)
def setpiece(name, objs):
    """join the objects into one node named set_<name>, so the page can show or hide it"""
    import bpy as _b
    _b.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    _b.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        _b.ops.object.join()
    o = _b.context.view_layer.objects.active
    o.name = o.data.name = f'set_{name}'
    o['caster'] = 0
    # the joined node stays in the active object's collections: a tree's leaf cards (far) can come first by name
    for c in list(o.users_collection):
        c.objects.unlink(o)
    _b.data.collections['dyn'].objects.link(o)
    return o

M_CLOTH = bl.mat('cloth', bl.tex_exists('cloth_base'), None, None, rough=0.95)
M_POT = bl.mat('pottery', color=(0.55, 0.36, 0.22), rough=0.8)
M_WALL = bl.mat('citywall', bl.tex_exists('outcrop_base'), bl.tex_exists('outcrop_nrm'), None, rough=0.9)

if RUN == 'field':
    # F2: the harvest feast spread on the grass and over the road: linen cloths, jars, bread baskets, cups
    feast = []
    for i, (x, y, w, d) in enumerate(((-3, 2.0, 2.4, 1.6), (0.5, -0.4, 2.0, 1.4), (3.5, 3.0, 2.2, 1.5))):
        feast.append(box(f'cloth{i}', x - w / 2, x + w / 2, y - d / 2, y + d / 2, terrain(x, y) + 0.005, terrain(x, y) + 0.02,
                         M_CLOTH, 'dyn', tile=2.0))
    for i, (x, y) in enumerate(((-3.6, 2.3), (-2.4, 1.6), (0.2, -0.6), (1.0, -0.1), (3.0, 3.3), (4.1, 2.6), (2.0, 4.4))):
        feast.append(bl.cyl(f'jar{i}', x, y, terrain(x, y), terrain(x, y) + rr.uniform(0.25, 0.5), 0.16, 0.09, 10, M_POT, 'dyn'))
    for i, (x, y) in enumerate(((-2.8, 1.5), (0.8, -0.8), (3.8, 3.4))):
        feast.append(bl.cyl(f'basket{i}', x, y, terrain(x, y), terrain(x, y) + 0.18, 0.22, 0.26, 10, M['bark'], 'dyn'))
    setpiece('feast', feast)
    # F3: the brook across the road, 1.8 m wide, stepping stones
    brook = [box('brookbed', -0.9, 0.9, -WIDE, WIDE, -0.18, -0.12, bl.mat('brookwater', color=(0.1, 0.12, 0.1), rough=0.05),
                 'dyn', tile=1.0)]
    for i, y in enumerate((-0.9, 0.0, 0.9)):
        brook.append(rock(f'brookstone{i}', 0.1 * (-1) ** i, y, -0.08, 0.28, M['rock'], squash=0.45, seed=300 + i,
                          group='dyn', caster=False, subdiv=1))
    setpiece('brook', brook)
    # F5: rock-cut tombs in a low limestone bank, cypresses
    tombs = []
    for s in (-1, 1):
        tombs.append(box(f'tombbank{s}', -HALF + 2, HALF - 2, s * 6.5 - 1, s * 6.5 + 1, -0.3, 2.2, M['rock'], 'dyn', tile=2.0))
        for i, x in enumerate((-10, -3, 5, 12)):
            tombs.append(box(f'tombdoor{s}{i}', x - 0.5, x + 0.5, s * 5.48 - 0.03, s * 5.48 + 0.03, 0.1, 1.5,
                             bl.mat('tombdark', color=(0.08, 0.07, 0.06), rough=1.0), 'dyn', tile=1.0))
        for i, x in enumerate((-14, -6, 2, 9, 16)):
            tombs.append(rk.cypress(f'tombcypress{s}{i}', x, s * 9.0, 0.0, rr.uniform(10, 13), M['cypress'], group='dyn'))
    setpiece('tombs', tombs)
    # F6: the city wall and the west gate, its passage facing back along the road (towards the low sun)
    gate = [box('wall_s', -2, 2, -40, -2.2, -0.5, 9, M_WALL, 'dyn', tile=3.0), box('wall_n', -2, 2, 2.2, 40, -0.5, 9, M_WALL, 'dyn', tile=3.0),
            box('gate_top', -2, 2, -2.2, 2.2, 5.0, 9, M_WALL, 'dyn', tile=3.0, bottom=True),
            box('tower_s', -3.5, 3.5, -9, -3, -0.5, 14, M_WALL, 'dyn', tile=3.0),
            box('tower_n', -3.5, 3.5, 3, 9, -0.5, 14, M_WALL, 'dyn', tile=3.0)]
    setpiece('gate', gate)
    # F1': the narrow path through the wheat: stalks over the road's edges, a path under 1 m left
    short = [(x, s * y, 0.0) for x in [i * 0.6 - HALF + 0.3 for i in range(60)] for s in (-1, 1) for y in (0.55, 1.1, 1.65, 2.2)]
    setpiece('shortcut', [rk.cards('shortwheat', short, M['wheat'], h=(0.85, 1.05), w=(0.6, 0.8), seed=14, group='dyn')])
    # the city far off: the wall's line and its towers, 1 unit = 1 m at the city (the page scales it by the distance)
    city = []
    for i, (y0, y1, h) in enumerate(((-120, -30, 11), (-30, 30, 12), (30, 140, 11))):
        city.append(box(f'city_wall{i}', -3, 3, y0, y1, 0, h, M_WALL, 'dyn', tile=6.0))
    for i, (y, h, w) in enumerate(((-110, 18, 7), (-50, 22, 8), (-8, 26, 9), (8, 26, 9), (60, 20, 8), (125, 18, 7))):
        city.append(box(f'city_tower{i}', -w / 2, w / 2, y - w / 2, y + w / 2, 0, h, M_WALL, 'dyn', tile=6.0))
    setpiece('city', city)
elif RUN == 'night':
    # the stretch with the spring: three planes and the rock, silhouettes under the stars
    spring = []
    for i, (x, y, h) in enumerate(((-6, 7, 16), (-9, 11, 18), (-4, 13, 14))):
        o = tree(f'nightplane{i}', x, y, h, h * 0.36, M['holm'], M['bark'], 'round', z=terrain(x, y), group='dyn')
        spring += [p for p in bpy.data.objects if p.name.startswith(f'nightplane{i}')]
    spring.append(rock('nightledge', 2, 6.5, terrain(2, 6.5) + 0.3, 1.4, M['rock'], squash=0.8, seed=400, group='dyn'))
    setpiece('spring', spring)
    # the top of the pass: the two rocks of the gate, low, against the stars, the road between them
    top = [rock('nightgate_n', 0, 4.2, 1.0, 3.2, M['rock'], squash=1.3, seed=410, group='dyn'),
           rock('nightgate_s', 0, -4.0, 0.8, 2.8, M['rock'], squash=1.3, seed=420, group='dyn')]
    setpiece('passtop', top)

# the tile's own foliage cards (dyn) are joined per material: they scroll with the tile
def join_tile(prefix):
    objs = [o for o in bpy.data.objects if o.name.startswith(prefix) and o.type == 'MESH']
    if objs:
        setpiece('x', objs).name = prefix.rstrip('_')
for prefix in ('tile_palm', 'tile_cypress', 'tile_sheaf'):
    join_tile(prefix)
for o in bpy.data.objects:
    if o.name.startswith('tile_') and o.data:
        o.data.name = o.name

bl.save(f'{OUT}/{STEM}_raw.blend')
