# Shared pieces for the road's other stops and run segments (F-15): the pass, the spring, the run tiles. The river
# (build_road_river.py, F-10) keeps its own copies; these follow the same rules (bl.py groups, plan frame of
# homeward-road.md 0: +x = towards Syracuse, z = 0 at the landing).
import bpy, bmesh, math, random   # bpy first: it brings mathutils
from mathutils import Vector, noise
import bl
from bl import heightfield, lines


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


def seg_dist(px, py, pts):
    """distance from (px, py) to a polyline, and the parameter (0..1 over the whole line) of the nearest point"""
    best, best_t, acc = 1e9, 0.0, 0.0
    lens = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    total = sum(lens) or 1.0
    for (a, b), L in zip(zip(pts, pts[1:]), lens):
        ex, ey = b[0] - a[0], b[1] - a[1]
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - a[0]) * ex + (py - a[1]) * ey) / (L * L)))
        d = math.hypot(px - a[0] - t * ex, py - a[1] - t * ey)
        if d < best:
            best, best_t = d, (acc + t * L) / total
        acc += L
    return best, best_t


def materials():
    """the roadside materials every stop has (road-common, homeward-road.md 0.4) and the far hills; texture keys:
    road_tex.py"""
    pbr, mat, tex = bl.pbr, bl.mat, bl.tex_exists
    return dict(
        road=pbr('floor', 'road'),        # named floor: the page's ambient ground colour reads materials.floor
        gravel=pbr('gravel', 'gravel'),
        grass=pbr('grass', 'grass'),
        rock=pbr('outcrop', 'outcrop'),
        bark=mat('bark', tex('bark_base'), tex('wood_nrm'), None, rough=0.9),
        holm=mat('holmoak', tex('holmoak_base'), None, None, rough=0.85),
        palm=mat('palm', tex('palm_base'), None, None, rough=0.8),
        wheat=mat('wheat', tex('wheat_base'), None, None, rough=0.9),
        cypress=mat('cypress', tex('cypress_base'), None, None, rough=0.9),
        hill=mat('hill', tex('hill_base'), tex('outcrop_nrm'), None, rough=0.95),
    )


def far_ring(name, hfun, mats, matfun, half=40, reach=340, tile=12.0):
    """the far land round the near ground: a coarse grid with a hole where the near ground is (far group: not baked).
    hfun gets plan metres; matfun(cx, cy, cz) -> index into mats (the page's land.ts shades the 'hill' material)"""
    FX = lines((-reach, -100, 30.0), (-100, 100, 12.0), (100, reach, 30.0), extra=(-half, half))
    FY = lines((-reach, -100, 30.0), (-100, 100, 12.0), (100, reach, 30.0), extra=(-half, half))
    heightfield(name, FX, FY, hfun, matfun, mats, 'far', skip=lambda cx, cy: abs(cx) < half and abs(cy) < half,
                tile=tile, tris=True)
    return FX, FY


def hills(x, y, base, rng_seed=2.2, high=(0.0, 0.0), low=(0.0, 0.0)):
    """rolling hills beyond 40 m: rising with distance, higher towards the plan angle high[0] (degrees) by high[1]
    (a tangent), lower towards low[0] by low[1]"""
    d = math.hypot(x, y)
    if d <= 40:
        return base
    a = math.degrees(math.atan2(y, x))
    def bump(c, w=70):
        dd = abs((a - c + 180) % 360 - 180)
        return math.cos(dd / w * math.pi / 2) if dd < w else 0.0
    n = noise.noise(Vector((x / 60, y / 60, rng_seed))) * 0.5 + 0.5
    n2 = noise.noise(Vector((x / 17, y / 17, rng_seed + 3)))
    t = 0.05 + high[1] * bump(high[0]) - low[1] * bump(low[0])
    return base + (d - 40) * t * ss(d, 40, 200) * (0.8 + 0.3 * n + 0.1 * n2)


def shrub(name, x, y, z, r, m_leaf, m_bark, group='arch'):
    """a low bush (mastic, thyme): a holm-oak crown sat on the ground"""
    return bl.tree(name, x, y, r * 1.6, r, m_leaf, m_bark, 'round', z=z - r * 0.55, group=group)


def palm(name, x, y, z, r, m, seed=0, group='far'):
    """a dwarf fan palm (Chamaerops humilis): fronds as crossed alpha cards fanning out of the ground"""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    rr = random.Random(seed * 7919 + int(x * 10) * 31 + int(y * 10))
    for k in range(9):
        a = 2 * math.pi * k / 9 + rr.uniform(-0.2, 0.2)
        tilt = rr.uniform(0.35, 0.9)
        L = r * rr.uniform(0.8, 1.1)
        dx, dy = math.cos(a), math.sin(a)
        tip = Vector((x + dx * L * math.cos(tilt), y + dy * L * math.cos(tilt), z + 0.25 + L * math.sin(tilt)))
        w = L * 0.45
        side = Vector((-dy, dx, 0)) * w
        mid = Vector((x, y, z + 0.2))
        vs = [bm.verts.new(mid - side * 0.15), bm.verts.new(mid + side * 0.15), bm.verts.new(tip + side), bm.verts.new(tip - side)]
        f = bm.faces.new(vs)
        for l, uv in zip(f.loops, ((0.45, 0), (0.55, 0), (1, 1), (0, 1))):
            l[uvl].uv = uv
    bm.normal_update()
    return bl.obj_from_bm(name, bm, [m], group)


def cards(name, spots, m, h=(0.9, 1.2), w=(0.8, 1.2), seed=1, group='far'):
    """crossed upright alpha cards (wheat, grass tufts, ferns) at spots [(x, y, z)]"""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    rr = random.Random(seed)
    for x, y, z in spots:
        hh, ww = rr.uniform(*h), rr.uniform(*w)
        a0 = rr.uniform(0, math.pi)
        for a in (a0, a0 + math.pi / 2):
            dx, dy = math.cos(a) * ww / 2, math.sin(a) * ww / 2
            vs = [bm.verts.new((x - dx, y - dy, z - 0.05)), bm.verts.new((x + dx, y + dy, z - 0.05)),
                  bm.verts.new((x + dx, y + dy, z + hh)), bm.verts.new((x - dx, y - dy, z + hh))]
            f = bm.faces.new(vs)
            u0 = rr.choice((0.0, 0.5))
            for l, uv in zip(f.loops, ((u0, 0), (u0 + 0.5, 0), (u0 + 0.5, 1), (u0, 1))):
                l[uvl].uv = uv
    bm.normal_update()
    return bl.obj_from_bm(name, bm, [m], group)


def cypress(name, x, y, z, h, m, group='far'):
    """a cypress: a tall narrow spindle (far: a dark upright stroke)"""
    bm = bmesh.new()
    rings = []
    for k in range(7):
        t = k / 6
        r = h * 0.09 * math.sin(math.pi * min(1.0, t * 1.05 + 0.08)) ** 0.8
        rings.append([bm.verts.new((x + r * math.cos(2 * math.pi * i / 8), y + r * math.sin(2 * math.pi * i / 8), z + t * h)) for i in range(8)])
    for a, b in zip(rings, rings[1:]):
        for i in range(8):
            j = (i + 1) % 8
            bm.faces.new((a[i], a[j], b[j], b[i]))
    for f in bm.faces:
        f.smooth = True
    bm.normal_update()
    bl.box_uv_bm(bm, 1.6)
    return bl.obj_from_bm(name, bm, [m], group, True)


def steps(name, pts, zfun, m, every=1.6, width=2.0, group='arch'):
    """stone steps along a path: a low slab across the path every so often, sitting on the ground"""
    out = []
    lens = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    k = 0
    for (a, b), L in zip(zip(pts, pts[1:]), lens):
        n = max(1, int(L / every))
        dx, dy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        for i in range(n):
            t = (i + 0.5) / n
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            z = zfun(x, y)
            from mathutils import Matrix
            xf = Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.atan2(dy, dx), 4, 'Z')
            out.append(bl.box(f'{name}{k}', -0.18, 0.18, -width / 2, width / 2, -0.25, 0.12, m, group, tile=1.0,
                              caster=False, xform=xf))
            k += 1
    return out
