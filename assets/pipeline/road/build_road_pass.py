# The mountain pass (F-15, ux/scenes/homeward-road.md 2): act 4 only, 13:40 to 14:00 (beat.19, the bandits).
# Plan frame (homeward-road.md 0): +x = towards Syracuse = azimuth 80°, +y = its left (north-west), z = 0 at the
# landing (shelf-west). No rotation (layout rotationDeg 0), the sun scripts get SCENE_MINUS_X_AZ = 260.
# From the west: the road up out of the river valley, the shelf (the one flat place, a small holm oak), the fork with
# the shepherds' cairn, the zigzag with its stone steps up to the rock gate (two limestone masses, 4 m apart against
# the sky), the saddle; behind the rocks, in their shadow at 14:00, the ground where the bandits wait; the goat track
# (the side path) bends round the shoulder to the north and out of sight. South: a steep scree slope; north: rock.
import bpy, os, sys, math, random   # bpy first: it brings mathutils
from mathutils import Vector, noise
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common')]
import bl
import roadkit as rk
from bl import box, rock, tree, heightfield, lines
from roadkit import pl, ss, seg_dist

OUT = os.environ['PLAZA_OUT']
STEM = os.environ['SCENE_STEM']
random.seed(19)
bl.setup(f'{OUT}/tex')
M = rk.materials()
M_SCREE = bl.mat('scree', bl.tex_exists('gravel_base'), bl.tex_exists('outcrop_nrm'), None, rough=0.9)

# ---------------------------------------------------------------- the ground
ROAD = [(-60, -1.5), (-30, -1), (-16, -1), (-4, 0)]     # up from the valley to the fork (2.5 m wide)
ZIG = [(-4, 0), (3, -4), (7, 1), (11, 0), (13, 0)]    # the zigzag, 2 m wide, stone steps
DOWN = [(13, 0), (20, -0.5), (40, -2), (120, -6)]     # over the saddle and down towards the plain
SIDE = [(-5, 2), (-1, 8), (4, 13), (8, 16), (12, 22)]  # the goat track, under 1 m
SADDLE_Z = 7.0

def along_x(x):
    """the height of the way itself: the road up (-0.8 at x -30, 0 at the landing), the shelf at 1.2, the climb to the
    saddle at 7, then down the east side"""
    return pl(x, [(-60, -2.6), (-30, -0.8), (-20, 0.0), (-16, 0.4), (-14, 1.2), (-4, 1.2), (11, SADDLE_Z), (13, SADDLE_Z),
                  (20, 5.6), (40, 2.0), (80, -3.0)])

def zig_z(x, y):
    """on the zigzag the height goes by the distance walked, not by x (the turns climb too)"""
    _, t = seg_dist(x, y, ZIG[:4])
    return 1.2 + (SADDLE_Z - 1.2) * t

def side_z(x, y):
    _, t = seg_dist(x, y, SIDE)
    return pl(t, [(0, 1.2), (0.75, 3.0), (1.0, 3.6)])

def terrain(x, y):
    z = along_x(x)
    # the climb is a slope across the whole width; on the zigzag's line it is cut to the path's height
    dz, _ = seg_dist(x, y, ZIG[:4])
    if -5 < x < 12:
        z = z * (1 - ss(-dz, -2.2, -0.9)) + zig_z(x, y) * ss(-dz, -2.2, -0.9)
    # north: the rock wall and its scrub climb fast; south: the scree slope falls away
    z += ss(y, 6.0, 12.0) * 5.0 + max(0.0, y - 12.0) * 0.9
    z -= ss(-y, 6.0, 12.0) * 5.0 + max(0.0, -y - 12.0) * 0.7
    # the goat track: a ledge cut into the shoulder
    ds, _ = seg_dist(x, y, SIDE)
    if ds < 2.5 and y > 1.5:
        z = z * ss(ds, 0.6, 2.5) + side_z(x, y) * (1 - ss(ds, 0.6, 2.5))
    # the bandits' ground behind the rocks: dropped a little below the saddle, out of sight from the zigzag
    for cx, cy in ((16.5, 6.5), (16.0, -6.0)):
        k = 1 - ss(math.hypot(x - cx, y - cy), 2.0, 4.0)
        z = z * (1 - k) + (SADDLE_Z - 0.9) * k
    # a little roll everywhere off the ways
    off = min(seg_dist(x, y, ROAD)[0], dz, ds, seg_dist(x, y, DOWN)[0])
    z += 0.22 * noise.noise(Vector((x / 6, y / 6, 1.7))) * ss(off, 1.5, 4.0)
    return z

def ground_mat(cx, cy, cz):
    if seg_dist(cx, cy, ROAD)[0] < 1.25 or seg_dist(cx, cy, DOWN)[0] < 1.25:
        return 0
    if seg_dist(cx, cy, ZIG[:4])[0] < 1.0 or (cx > 11 and abs(cy) < 1.6):
        return 1
    if seg_dist(cx, cy, SIDE)[0] < 0.45 and cy > 1.5:
        return 0
    if cy < -6:
        return 3      # scree
    if cy > 8 or (cx > 6 and cz > 4.5):
        return 4      # bare rock
    return 2

GMATS = [M['road'], M['gravel'], M['grass'], M_SCREE, M['rock']]
XS = lines((-40, -18, 2.0), (-18, 16, 0.5), (16, 40, 2.0))
YS = lines((-40, -12, 3.0), (-12, 18, 0.5), (18, 40, 3.0))
heightfield('ground', XS, YS, terrain, ground_mat, GMATS, 'ground', tile=3.0)

# ---------------------------------------------------------------- the far land: the river valley back west (its
# brown water, the rain cloud gone behind the far hills), rock and scrub north, the hot pale plain east and below
def far_height(x, y):
    z = terrain(x, y) if abs(x) < 60 and abs(y) < 60 else along_x(x)
    d = math.hypot(x, y)
    a = math.degrees(math.atan2(y, x))
    north = math.cos(math.radians(a - 90)) if abs((a - 90 + 180) % 360 - 180) < 90 else 0.0
    east = math.cos(math.radians(a)) if abs((a + 180) % 360 - 180) < 90 else 0.0
    west = math.cos(math.radians(a - 180)) if abs((a + 180) % 360 - 180) > 90 else 0.0
    n = noise.noise(Vector((x / 50, y / 50, 4.4))) * 0.5 + 0.5
    if d > 40:
        z += (d - 40) * (0.12 * north + 0.04) * (0.7 + 0.5 * n) * ss(d, 40, 160)
        z -= (d - 40) * 0.11 * east * ss(d, 40, 200)                # the plain falls away east
        z -= (d - 40) * 0.05 * west * ss(d, 40, 120) * (1 - ss(d, 160, 300))   # the valley back west, hills beyond
        z += (d - 160) * 0.18 * west * ss(d, 160, 300)
    return z

def far_mat(cx, cy, cz):
    return 0 if abs(cy - pl(cx, [(-340, 0), (-60, -1.5), (60, -2), (340, -8)])) < 3 and abs(cx) > 40 else (2 if cz > 8 else 1)

rk.far_ring('far_land', far_height, [M['road'], M['grass'], M['hill']], far_mat)

# ---------------------------------------------------------------- the rock gate (two limestone masses, 4 m apart)
def mass(name, x0, x1, y0, y1, top, seed):
    """a rock mass of a few lumpy outcrops, its top about `top` over the saddle"""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rr = random.Random(seed)
    for k in range(5):
        x = rr.uniform(x0 + 1, x1 - 1); y = rr.uniform(y0 + 0.6, y1 - 0.6)
        r = rr.uniform(1.6, 2.4)
        rock(f'{name}{k}', x, y, SADDLE_Z + rr.uniform(0.2, top - r * 0.9), r, M['rock'], squash=1.25, seed=seed + k)
    rock(f'{name}_core', cx, cy, SADDLE_Z + top * 0.35, max(x1 - x0, y1 - y0) * 0.42, M['rock'], squash=1.1, seed=seed + 9)
mass('gate_n', 8, 14, 2.2, 6, 5.0, 31)
mass('gate_s', 8.5, 13.5, -5.8, -2.4, 4.0, 47)
# the cleft on the north rock's west face (8, 3.2): two slabs leaning apart
for i, (x, y) in enumerate(((7.6, 2.7), (7.8, 3.8))):
    rock(f'cleft{i}', x, y, terrain(x, y) + 0.8, 0.9, M['rock'], squash=1.6, seed=60 + i)

# north wall: a row of outcrops along the scrub line
for i in range(9):
    x = -16 + i * 3.6 + random.uniform(-0.8, 0.8)
    y = 9.5 + random.uniform(0, 3.5)
    if seg_dist(x, y, SIDE)[0] < 2.2:
        continue
    rock(f'wall_n{i}', x, y, terrain(x, y) + 0.2, random.uniform(1.0, 1.8), M['rock'], squash=0.9, seed=70 + i)
# loose boulders on the scree
for i in range(7):
    x = random.uniform(-20, 14); y = random.uniform(-14, -7.5)
    rock(f'boulder{i}', x, y, terrain(x, y) - 0.1, random.uniform(0.4, 0.9), M['rock'], squash=0.7, seed=90 + i)

# ---------------------------------------------------------------- the shelf, the fork, the steps
# the small holm oak, the pass's one shade (13:40: its shadow falls to its north-east)
tree('holm', -11, 4.5, 5.0, 2.5, M['holm'], M['bark'], 'round', z=terrain(-11, 4.5))
# the cairn at the fork: five stones stacked, the shepherds' sign
cz = terrain(-5.5, 3.0)
for i, (r, dz) in enumerate(((0.38, 0.1), (0.32, 0.45), (0.27, 0.75), (0.22, 1.0), (0.15, 1.2))):
    rock(f'cairn{i}', -5.5 + 0.04 * i, 3.0 - 0.03 * i, cz + dz, r, M['rock'], squash=0.7, seed=110 + i, subdiv=1)
rk.steps('step', ZIG[:4], lambda x, y: zig_z(x, y), M['gravel'], every=1.7, width=1.9)

# ---------------------------------------------------------------- scrub: dwarf fan palms, mastic and thyme
rr = random.Random(23)
pal, bush = 0, 0
for _ in range(80):
    x, y = rr.uniform(-34, 30), rr.uniform(-16, 18)
    near_way = min(seg_dist(x, y, ROAD)[0], seg_dist(x, y, ZIG)[0], seg_dist(x, y, SIDE)[0], seg_dist(x, y, DOWN)[0])
    if near_way < 1.8 or (-29 < x < -18 and abs(y + 1) < 3.5) or (7 < x < 19 and -7 < y < 8):
        continue   # the ways; 9 m behind the landing only road and low grass; the gate and the bandits' ground clear
    if -16 < x < -4 and -5 < y < 5:
        continue   # the shelf stays open to walk and talk on
    z = terrain(x, y)
    if rr.random() < 0.45:
        rk.palm(f'palm{pal}', x, y, z, rr.uniform(0.7, 1.1), M['palm'], seed=pal); pal += 1
    else:
        rk.shrub(f'bush{bush}', x, y, z, rr.uniform(0.5, 0.9), M['holm'], M['bark']); bush += 1
# the holm-oak scrub the goat track turns into, out of sight at (8, 16)
for i, (x, y) in enumerate(((9.5, 15.0), (8.0, 17.6), (10.5, 18.2), (6.6, 18.8))):
    tree(f'scrub{i}', x, y, random.uniform(3.0, 4.0), 1.8, M['holm'], M['bark'], 'round', z=terrain(x, y))

bl.save(f'{OUT}/{STEM}_raw.blend')
