# The spring (F-15, ux/scenes/homeward-road.md 3): act 4, 14:55 to 16:30 (beat.20 Melos falls, beat.21 he drinks).
# Plan frame (homeward-road.md 0): +x = towards Syracuse = azimuth 100°, +y = its left (north-north-east), z = 0 at
# the landing (road-spring). No rotation (layout rotationDeg 0), the sun scripts get SCENE_MINUS_X_AZ = 280.
# The road comes down off the pass and levels out; north of it a meadow of dry grass rising gently, a low limestone
# ledge with the spring welling out of a crack at its foot into a small clear pool, a trickle running down across
# the road over stepping stones and into the ditch beyond the dry-stone wall; three oriental planes west of the spring
# (at 16:30 the sun is behind them and lights their leaves through); wheat beyond the wall; east a low rise hides
# the plain (no tower yet).
import bpy, os, sys, math, random   # bpy first: it brings mathutils
from mathutils import Vector, noise
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common')]
import bl
import roadkit as rk
from bl import box, rock, tree, heightfield, lines
from roadkit import pl, ss, seg_dist

OUT = os.environ['PLAZA_OUT']
STEM = os.environ['SCENE_STEM']
random.seed(21)
bl.setup(f'{OUT}/tex')
M = rk.materials()
tex = bl.tex_exists
M_WETROCK = bl.mat('wetrock', tex('wetrock_base'), tex('outcrop_nrm'), None, rough=0.45)
M_LUSH = bl.mat('lushgrass', tex('lushgrass_base'), tex('grass_nrm'), None, rough=0.85)
M_PLANE = bl.mat('plane', tex('plane_base'), None, None, rough=0.8)
M_PLANEBARK = bl.mat('planebark', tex('planebark_base'), tex('wood_nrm'), None, rough=0.85)
M_FERN = bl.mat('fern', tex('fern_base'), None, None, rough=0.8)
M_POOLBED = bl.mat('poolbed', tex('pebbles_base'), tex('pebbles_nrm'), None, rough=0.4)
M_WATER = bl.mat('water', color=(0.05, 0.07, 0.06), rough=0.05)   # the page's shader replaces it

ROAD_Y = -4.0
POOL = (0.0, 5.3, 0.6)                     # centre, radius (diameter 1.2 m)
POOL_LEVEL = 0.27                          # layout.json water.levelM: 12 cm under the meadow there
STREAM = [(0.3, 4.8), (2.5, 2.5), (5.0, 0.0), (6.5, -2.5), (7.2, -5.5), (7.6, -8.5)]
WALL_Y = -6.5

def road_z(x):
    return pl(x, [(-60, 4.0), (-28, 2.0), (-12, 0.0), (24, -0.6), (60, -0.2)])

def meadow_z(x, y):
    """north of the road the meadow rises gently (z +1.2 at y 16), and towards the east a low rise (x 20) hides the
    plain"""
    return road_z(x) + 0.075 * max(0.0, y - ROAD_Y - 1.5) + 0.9 * ss(x, 14, 22) * (1 - ss(x, 30, 40))

def terrain(x, y):
    z = meadow_z(x, y) if y > ROAD_Y + 1.5 else road_z(x) + (meadow_z(x, y) - road_z(x)) * ss(y, ROAD_Y + 1.5, ROAD_Y + 3)
    # south of the wall the wheat field sits a little lower
    z -= 0.35 * ss(-y, -WALL_Y - 0.2, -WALL_Y + 1.5)
    # the pool: a bowl 35 cm under the water; the trickle: a little runnel cut into the grass
    dp = math.hypot(x - POOL[0], y - POOL[1])
    if dp < 1.4:
        k = ss(dp, POOL[2] + 0.1, 1.4)
        z = z * k + (POOL_LEVEL - 0.35) * (1 - k)
    ds, _ = seg_dist(x, y, STREAM)
    if ds < 0.5 and dp > 0.5:
        z -= 0.12 * (1 - ss(ds, 0.12, 0.5))
    z += 0.12 * noise.noise(Vector((x / 4, y / 4, 0.9))) * ss(abs(y - ROAD_Y), 1.8, 3.5) * ss(dp, 1.0, 2.5)
    return z

def ground_mat(cx, cy, cz):
    if abs(cy - ROAD_Y) < 1.5:
        return 0
    if abs(cy - ROAD_Y) < 2.0:
        return 1
    if seg_dist(cx, cy, STREAM)[0] < 0.9 or math.hypot(cx - POOL[0], cy - POOL[1]) < 1.6:
        return 3       # green along the water
    return 2

GMATS = [M['road'], M['gravel'], M['grass'], M_LUSH]
XS = lines((-40, -20, 2.0), (-20, 22, 0.5), (22, 40, 2.0), extra=(-0.6, 0.6))
YS = lines((-40, -9, 2.0), (-9, 17, 0.5), (17, 40, 3.0), extra=(4.7, 5.9))
heightfield('ground', XS, YS, terrain, ground_mat, GMATS, 'ground', tile=3.0)

# ---------------------------------------------------------------- far land: behind (west, up) the pass and its ridge;
# north the slope with olive terraces; south the wheat over the wall and low hills; east the rise
def far_height(x, y):
    z = terrain(x, y) if abs(x) < 60 and abs(y) < 60 else road_z(x)
    return rk.hills(x, y, z, 3.3, high=(160, 0.16), low=(0, 0.04))

def far_mat(cx, cy, cz):
    return 2 if cz > 6 else 1

rk.far_ring('far_land', far_height, [M['road'], M['grass'], M['hill']], far_mat)

# ---------------------------------------------------------------- the dry-stone wall south of the road
for i, (x0, x1) in enumerate(((-18, -6.5), (-6.5, 5.6), (8.6, 16))):   # a gap where the trickle goes under
    z0 = min(terrain(x0, WALL_Y), terrain(x1, WALL_Y)) - 0.25
    box(f'wall{i}', x0, x1, WALL_Y - 0.3, WALL_Y + 0.3, z0, road_z((x0 + x1) / 2) + 0.8, M['rock'], tile=1.6, caster=True)
box('wall_lintel', 5.6, 8.6, WALL_Y - 0.3, WALL_Y + 0.3, road_z(7) + 0.25, road_z(7) + 0.8, M['rock'], tile=1.6,
    caster=True, bottom=True)

# ---------------------------------------------------------------- the spring: ledge, crack, pool, trickle
LX0, LX1, LY0, LY1 = -3.5, 1.5, 6.2, 8.4
for i in range(4):
    x = LX0 + 0.8 + i * 1.3
    rock(f'ledge{i}', x, 7.4 + 0.25 * math.sin(i * 1.7), terrain(x, 7.4) + 0.35, 1.05, M['rock'], squash=0.95, seed=130 + i)
# the wet face round the crack (-0.4, 6.1): darker, moss and maidenhair fern
for i, (x, y) in enumerate(((-1.1, 6.55), (0.3, 6.6))):
    rock(f'wetface{i}', x, y, POOL_LEVEL + 0.35, 0.6, M_WETROCK, squash=1.1, seed=140 + i)
rk.cards('fern', [(-1.6, 6.3, POOL_LEVEL + 0.25), (-1.3, 6.15, POOL_LEVEL + 0.5), (0.8, 6.3, POOL_LEVEL + 0.3),
                  (1.1, 6.4, POOL_LEVEL + 0.6), (-0.9, 6.0, POOL_LEVEL + 0.05), (0.5, 6.0, POOL_LEVEL + 0.05)],
         M_FERN, h=(0.25, 0.4), w=(0.35, 0.5), seed=4)
# the pool's bed of small stones, seen through the water
heightfield('poolbed', lines((-0.75, 0.75, 0.25)), lines((4.55, 6.05, 0.25)),
            lambda x, y: POOL_LEVEL - 0.22 + 0.2 * ss(math.hypot(x - POOL[0], y - POOL[1]), 0.2, POOL[2]),
            lambda *a: 0, [M_POOLBED], 'arch', skip=lambda cx, cy: math.hypot(cx - POOL[0], cy - POOL[1]) > 0.75, tile=0.6)
# the water: the pool, and a ribbon along the trickle (its own node: the page's shader)
def water():
    import bmesh
    bm = bmesh.new()
    c = bm.verts.new((POOL[0], POOL[1], POOL_LEVEL))
    ring = [bm.verts.new((POOL[0] + POOL[2] * 1.05 * math.cos(2 * math.pi * i / 16),
                          POOL[1] + POOL[2] * 0.95 * math.sin(2 * math.pi * i / 16), POOL_LEVEL)) for i in range(16)]
    for i in range(16):
        bm.faces.new((c, ring[i], ring[(i + 1) % 16]))
    prev = None
    path = []
    for a, b in zip(STREAM, STREAM[1:]):
        for k in range(4):
            t = k / 4
            path.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    path.append(STREAM[-1])
    for i, (x, y) in enumerate(path):
        nx, ny = path[min(i + 1, len(path) - 1)][0] - path[max(i - 1, 0)][0], path[min(i + 1, len(path) - 1)][1] - path[max(i - 1, 0)][1]
        L = math.hypot(nx, ny) or 1
        ox, oy = -ny / L * 0.13, nx / L * 0.13
        z = terrain(x, y) + 0.03
        pair = [bm.verts.new((x - ox, y - oy, z)), bm.verts.new((x + ox, y + oy, z))]
        if prev:
            bm.faces.new((prev[0], pair[0], pair[1], prev[1]))
        prev = pair
    bm.normal_update()
    bl.box_uv_bm(bm, 1.0)
    o = bl.obj_from_bm('water', bm, [M_WATER], 'dyn')
    o['caster'] = 0
water()
# stepping stones where the trickle crosses the road
for i, (x, y) in enumerate(((5.6, -3.0), (6.2, -3.9), (6.6, -4.8))):
    rock(f'stepstone{i}', x, y, road_z(x) - 0.05, 0.3, M['rock'], squash=0.45, seed=150 + i, subdiv=1)

# ---------------------------------------------------------------- trees and scrub
for i, (x, y, h) in enumerate(((-13, 6, 16.0), (-16, 10.5, 18.0), (-11, 12, 14.0))):
    tree(f'plane{i}', x, y, h, h * 0.36, M_PLANE, M_PLANEBARK, 'spread', z=terrain(x, y),
         lean=(random.uniform(-0.08, 0.08), random.uniform(-0.08, 0.08)))
# olives up the slope to the north (terraces beyond the meadow) and along the far side of the wall
for i, (x, y) in enumerate(((-4, 18), (4, 19), (12, 17.5), (20, 15), (-22, 9), (22, -12), (-24, -11))):
    tree(f'olive{i}', x, y, random.uniform(4.0, 5.5), 2.4, M['holm'], M['bark'], 'round', z=terrain(x, y))
for i, (x, y) in enumerate(((10, 9), (14.5, 4), (-7, 14), (17, 10.5))):
    rk.shrub(f'bush{i}', x, y, terrain(x, y), random.uniform(0.5, 0.8), M['holm'], M['bark'])
# wheat beyond the wall: crossed cards in rows (far group, not baked)
rr = random.Random(8)
wheat = [(x + rr.uniform(-0.3, 0.3), y + rr.uniform(-0.3, 0.3), 0.0) for x in range(-30, 31, 1) for y in (-8.0, -9.2, -10.4, -11.6, -12.8)]
rk.cards('wheat', [(x, y, terrain(x, y)) for x, y, _ in wheat if not (6.6 < x < 8.6)], M['wheat'], h=(0.8, 1.0), w=(0.9, 1.1), seed=8)
# tufts of dry grass and flowers in the meadow (low cards; none 9 m behind the landing, none round the talk spot)
tufts = []
for _ in range(160):
    x, y = rr.uniform(-16, 18), rr.uniform(-1.8, 16)
    if (-22 < x < -10 and y < 0) or math.hypot(x - 3.0, y - 3.2) < 2.0 or seg_dist(x, y, STREAM)[0] < 0.5 or math.hypot(x, y - 5.3) < 1.4:
        continue
    tufts.append((x, y, terrain(x, y)))
rk.cards('tufts', tufts, M['wheat'], h=(0.3, 0.5), w=(0.4, 0.6), seed=9)
# a cypress or two far off, upright dark strokes
for i, (x, y) in enumerate(((-34, 26), (36, 30), (30, -28))):
    rk.cypress(f'cypress{i}', x, y, far_height(x, y), random.uniform(11, 14), M['cypress'])

bl.save(f'{OUT}/{STEM}_raw.blend')
