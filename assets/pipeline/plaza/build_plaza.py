# Build the Syracuse plaza in Blender, headless (from the S7 realism spike; ux/art-direction 4.1).
# Local frame: the gate street runs along -X (azimuth 294°), north = +Y. The whole scene is rotated by 144°
# at the end so local -X points at 294°; sunpos.py and sky.py use the same rotation.
import bpy, bmesh, math, random, os, sys
from mathutils import Vector, Matrix, noise

OUT = os.environ['PLAZA_OUT']  # work dir (build.sh sets it); nothing here is committed
T = f'{OUT}/tex'  # placeholder_tex.py output: scans where we have them, placeholders otherwise
random.seed(7)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------------------------------------------------------------- materials
_imgs = {}
def img(name, noncolor=False):
    path = f'{T}/{name}'
    if path not in _imgs:
        im = bpy.data.images.load(path)
        if noncolor:
            im.colorspace_settings.name = 'Non-Color'
        _imgs[path] = im
    return _imgs[path]

def tex_exists(n):
    for ext in ('.jpg', '.png'):
        if os.path.exists(f'{T}/{n}{ext}'):
            return n + ext
    return None

MATS = {}
def mat(name, base=None, nrm=None, mr=None, color=(0.8, 0.8, 0.8), rough=0.85, metal=0.0):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    bsdf = N['Principled BSDF']
    uv = N.new('ShaderNodeUVMap'); uv.uv_map = 'UVMap'
    if base:
        t = N.new('ShaderNodeTexImage'); t.image = img(base)
        L.new(uv.outputs['UV'], t.inputs['Vector']); L.new(t.outputs['Color'], bsdf.inputs['Base Color'])
    else:
        bsdf.inputs['Base Color'].default_value = (*color, 1)
    if nrm:
        tn = N.new('ShaderNodeTexImage'); tn.image = img(nrm, True)
        L.new(uv.outputs['UV'], tn.inputs['Vector'])
        nm = N.new('ShaderNodeNormalMap'); nm.uv_map = 'UVMap'
        L.new(tn.outputs['Color'], nm.inputs['Color']); L.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    if mr:
        tm = N.new('ShaderNodeTexImage'); tm.image = img(mr, True)
        L.new(uv.outputs['UV'], tm.inputs['Vector'])
        sep = N.new('ShaderNodeSeparateColor')
        L.new(tm.outputs['Color'], sep.inputs['Color'])
        L.new(sep.outputs['Green'], bsdf.inputs['Roughness'])
        L.new(sep.outputs['Blue'], bsdf.inputs['Metallic'])
    else:
        bsdf.inputs['Roughness'].default_value = rough
        bsdf.inputs['Metallic'].default_value = metal
    MATS[name] = m
    return m

def pbr(name, key, base_key=None, **kw):
    b = tex_exists(f'{base_key or key}_base')
    return mat(name, b, tex_exists(f'{key}_nrm'), tex_exists(f'{key}_mr'), **kw)

M_FLOOR = pbr('floor', 'floor')
M_ASHLAR = pbr('ashlar', 'ashlar')
M_ASHLAR2 = pbr('ashlar_warm', 'ashlar', 'ashlar2')
M_PLAIN = pbr('stone', 'plain')
M_PLASTER = pbr('plaster', 'plain', 'plaster')
M_ROOF = pbr('roof', 'roof', 'roofwarm')
M_DOORS = pbr('doors', 'doors')
M_CORNICE = pbr('cornice', 'cornice')
M_TRIM = pbr('trim', 'trim')
M_FAB_R = pbr('fabric_red', 'fabric_red')
M_FAB_B = mat('fabric_blue', tex_exists('fabric_blue_base'), tex_exists('fabric_red_nrm'), tex_exists('fabric_blue_mr'))
M_WATER = mat('water', color=(0.05, 0.07, 0.07), rough=0.06)
M_HILL = mat('hill', tex_exists('hill_base'), tex_exists('plain_nrm'), None, rough=0.95)
M_BARK = mat('bark', tex_exists('bark_base'), tex_exists('plain_nrm'), None, rough=0.9)
M_CYPRESS = mat('cypress', tex_exists('cypress_base'), tex_exists('ivy_nrm'), None, rough=0.9)
M_OLIVE = mat('olive', tex_exists('olive_base'), tex_exists('ivy_nrm'), None, rough=0.85)
M_CLAY = mat('terracotta', tex_exists('plain_base'), tex_exists('plain_nrm'), None, color=(0.7, 0.4, 0.25), rough=0.8)

# ---------------------------------------------------------------- mesh helpers
COLL = {}
def coll(name):
    if name not in COLL:
        c = bpy.data.collections.new(name); scene.collection.children.link(c); COLL[name] = c
    return COLL[name]

def obj_from_bm(name, bm, mats, group, caster=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for m in mats:
        me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    coll(group).objects.link(o)
    o['caster'] = 1 if caster else 0
    return o

def box_uv_bm(bm, tile, uvname='UVMap', offset=(0, 0, 0)):
    uvl = bm.loops.layers.uv.get(uvname) or bm.loops.layers.uv.new(uvname)
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            co = l.vert.co + Vector(offset)
            if ax == 0:
                u, v = (co.y if n.x > 0 else -co.y), co.z
            elif ax == 1:
                u, v = (-co.x if n.y > 0 else co.x), co.z
            else:
                u, v = co.x, co.y
            l[uvl].uv = (u / tile, v / tile)

def box(name, x0, x1, y0, y1, z0, z1, m, group='arch', tile=4.0, caster=False, bottom=False):
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z)) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    def q(a, b, c, d):
        bm.faces.new((vs[a], vs[b], vs[c], vs[d]))
    q(0, 2, 3, 1) if bottom else None   # bottom
    q(4, 5, 7, 6)   # top
    q(0, 1, 5, 4)   # -y
    q(2, 6, 7, 3)   # +y
    q(0, 4, 6, 2)   # -x
    q(1, 3, 7, 5)   # +x
    bm.normal_update()
    box_uv_bm(bm, tile)
    return obj_from_bm(name, bm, [m], group, caster)

def cyl(name, cx, cy, z0, z1, r0, r1=None, seg=16, m=None, group='arch', tile=2.0, caster=False, cap=True):
    r1 = r0 if r1 is None else r1
    bm = bmesh.new()
    bot = [bm.verts.new((cx + r0 * math.cos(2 * math.pi * i / seg), cy + r0 * math.sin(2 * math.pi * i / seg), z0)) for i in range(seg)]
    top = [bm.verts.new((cx + r1 * math.cos(2 * math.pi * i / seg), cy + r1 * math.sin(2 * math.pi * i / seg), z1)) for i in range(seg)]
    uvl = bm.loops.layers.uv.new('UVMap')
    circ = 2 * math.pi * max(r0, r1)
    for i in range(seg):
        j = (i + 1) % seg
        f = bm.faces.new((bot[i], bot[j], top[j], top[i]))
        u0 = i / seg * circ / tile; u1 = (i + 1) / seg * circ / tile
        for l, uv in zip(f.loops, [(u0, z0 / tile), (u1, z0 / tile), (u1, z1 / tile), (u0, z1 / tile)]):
            l[uvl].uv = uv
    if cap:
        f = bm.faces.new(top)
        for l in f.loops:
            l[uvl].uv = (l.vert.co.x / tile, l.vert.co.y / tile)
    bm.normal_update()
    return obj_from_bm(name, bm, [m], group, caster)

def quad_uv(name, p0, ux, uy, w, h, uvrect, m, group='arch'):
    """quad with origin p0, unit axes ux (width) and uy (height); uvrect=(u0,v0,u1,v1)"""
    p0 = Vector(p0); ux = Vector(ux); uy = Vector(uy)
    bm = bmesh.new()
    vs = [bm.verts.new(p0), bm.verts.new(p0 + ux * w), bm.verts.new(p0 + ux * w + uy * h), bm.verts.new(p0 + uy * h)]
    f = bm.faces.new(vs)
    uvl = bm.loops.layers.uv.new('UVMap')
    u0, v0, u1, v1 = uvrect
    for l, uv in zip(f.loops, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]):
        l[uvl].uv = uv
    bm.normal_update()
    return obj_from_bm(name, bm, [m], group)

DOOR = (0.0, 0.012, 0.49, 0.94)       # arched door with fan light
SHUTTER = (0.50, 0.425, 0.905, 1.0)   # window with dark shutters
BARRED = (0.50, 0.0, 0.86, 0.41)      # small barred window

def gable_roof(name, x0, x1, y0, y1, z, pitch_deg=21, over=0.45, ridge_axis=None):
    """tiled gable roof + two gable walls (ashlar). Tiles run down the slope."""
    if ridge_axis is None:
        ridge_axis = 'x' if (x1 - x0) >= (y1 - y0) else 'y'
    X0, X1, Y0, Y1 = x0 - over, x1 + over, y0 - over, y1 + over
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    tile = 3.5
    tp = math.tan(math.radians(pitch_deg))
    if ridge_axis == 'x':
        half = (Y1 - Y0) / 2; ym = (Y0 + Y1) / 2; rz = z + half * tp; slope = half / math.cos(math.radians(pitch_deg))
        a, b, c, d = [bm.verts.new(v) for v in [(X0, Y0, z), (X1, Y0, z), (X1, ym, rz), (X0, ym, rz)]]
        e, f_, g, h = [bm.verts.new(v) for v in [(X1, Y1, z), (X0, Y1, z), (X0, ym, rz), (X1, ym, rz)]]
        for vs, along in [((a, b, c, d), (X0, X1)), ((e, f_, g, h), (X1, X0))]:
            fc = bm.faces.new(vs)
            uvs = [(along[0] / tile, 0), (along[1] / tile, 0), (along[1] / tile, slope / tile), (along[0] / tile, slope / tile)]
            for l, uv in zip(fc.loops, uvs):
                l[uvl].uv = uv
        bm.normal_update()
        roof = obj_from_bm(name + '_roof', bm, [M_ROOF], 'arch', True)
        # gable walls (triangles), slightly inset
        bm = bmesh.new()
        for xx, flip in [(x0, True), (x1, False)]:
            vs = [bm.verts.new(v) for v in [(xx, y0, z), (xx, y1, z), (xx, (y0 + y1) / 2, z + (y1 - y0) / 2 * tp)]]
            fc = bm.faces.new(vs if not flip else vs[::-1])
        bm.normal_update(); box_uv_bm(bm, 6.0)
        obj_from_bm(name + '_gable', bm, [M_ASHLAR], 'arch', True)
    else:
        half = (X1 - X0) / 2; xm = (X0 + X1) / 2; rz = z + half * tp; slope = half / math.cos(math.radians(pitch_deg))
        a, b, c, d = [bm.verts.new(v) for v in [(X1, Y0, z), (X1, Y1, z), (xm, Y1, rz), (xm, Y0, rz)]]
        e, f_, g, h = [bm.verts.new(v) for v in [(X0, Y1, z), (X0, Y0, z), (xm, Y0, rz), (xm, Y1, rz)]]
        for vs, along in [((a, b, c, d), (Y0, Y1)), ((e, f_, g, h), (Y1, Y0))]:
            fc = bm.faces.new(vs)
            uvs = [(along[0] / tile, 0), (along[1] / tile, 0), (along[1] / tile, slope / tile), (along[0] / tile, slope / tile)]
            for l, uv in zip(fc.loops, uvs):
                l[uvl].uv = uv
        bm.normal_update()
        roof = obj_from_bm(name + '_roof', bm, [M_ROOF], 'arch', True)
        bm = bmesh.new()
        for yy, flip in [(y0, False), (y1, True)]:
            vs = [bm.verts.new(v) for v in [(x0, yy, z), (x1, yy, z), ((x0 + x1) / 2, yy, z + (x1 - x0) / 2 * tp)]]
            fc = bm.faces.new(vs if not flip else vs[::-1])
        bm.normal_update(); box_uv_bm(bm, 6.0)
        obj_from_bm(name + '_gable', bm, [M_ASHLAR], 'arch', True)
    return roof

def facade_openings(name, wall, x0, x1, y0, y1, h, floors, door_every=2):
    """add door/window quads on the face of a building facing the plaza. wall in {'+x','-x','+y','-y'}"""
    eps = 0.03
    if wall in ('+x', '-x'):
        xx = (x1 + eps) if wall == '+x' else (x0 - eps)
        ux = (0, 1, 0) if wall == '+x' else (0, -1, 0)
        start, end = (y0, y1) if wall == '+x' else (y1, y0)
        length = abs(y1 - y0)
        def P(t, z):
            return (xx, start + (t if wall == '+x' else -t), z)
    else:
        yy = (y1 + eps) if wall == '+y' else (y0 - eps)
        ux = (-1, 0, 0) if wall == '+y' else (1, 0, 0)
        start = x1 if wall == '+y' else x0
        length = abs(x1 - x0)
        def P(t, z):
            return (start + (-t if wall == '+y' else t), yy, z)
    bays = max(1, int(length // 3.6))
    bw = length / bays
    k = 0
    for i in range(bays):
        c = (i + 0.5) * bw
        if i % door_every == 0:
            w, hh = 1.9, 3.6
            quad_uv(f'{name}_door{i}', P(c - w / 2, 0.02), ux, (0, 0, 1), w, hh, DOOR, M_DOORS)
        else:
            w, hh = 1.0, 1.15
            quad_uv(f'{name}_low{i}', P(c - w / 2, 1.5), ux, (0, 0, 1), w, hh, BARRED, M_DOORS)
        for fl in range(1, floors):
            z = fl * 3.3 + 0.6
            if z + 1.9 > h - 0.6:
                break
            w, hh = 1.25, 1.75
            quad_uv(f'{name}_win{i}_{fl}', P(c - w / 2, z), ux, (0, 0, 1), w, hh, SHUTTER, M_DOORS)
            k += 1

def building(name, x0, x1, y0, y1, h, faces, warm=False, floors=None):
    wm = M_ASHLAR2 if warm else (M_PLASTER if random.random() < 0.35 else M_ASHLAR)
    box(name + '_walls', x0, x1, y0, y1, 0, h, wm, tile=6.0, caster=True)
    box(name + '_plinth', x0 - 0.08, x1 + 0.08, y0 - 0.08, y1 + 0.08, 0, 0.7, M_PLAIN, tile=2.0)
    box(name + '_cornice', x0 - 0.18, x1 + 0.18, y0 - 0.18, y1 + 0.18, h - 0.35, h, M_PLAIN, tile=2.0)
    gable_roof(name, x0, x1, y0, y1, h)
    floors = floors or max(2, int(h // 3.3))
    for fw in faces:
        facade_openings(name, fw, x0, x1, y0, y1, h, floors)

# ---------------------------------------------------------------- ground
GX0 = -40.0     # ground lightmap covers x in [GX0, 34], y in [-32, 36] (local)

def ground():
    bm = bmesh.new()
    S = 120
    vs = [bm.verts.new(v) for v in [(-S, -S, 0), (S, -S, 0), (S, S, 0), (-S, S, 0)]]
    bm.faces.new(vs); bm.normal_update(); box_uv_bm(bm, 3.0)
    obj_from_bm('ground_far', bm, [M_FLOOR], 'far')
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in [(GX0, -32, 0.002), (34, -32, 0.002), (34, 36, 0.002), (GX0, 36, 0.002)]]
    bm.faces.new(vs); bm.normal_update(); box_uv_bm(bm, 3.0)
    obj_from_bm('ground', bm, [M_FLOOR], 'ground')

# ---------------------------------------------------------------- landmarks
# layout per ux/art-direction.md 4.1: west gate street on the sunset axis (local -X = 294°), castle and tower on the east
def city_gate(x=-34.0, half=3.6, h=9.0):
    for y0, y1 in ((-16, -half), (half, 16)):
        box(f'citywall{y0}', x - 1.2, x + 1.2, y0, y1, 0, h, M_ASHLAR2, tile=6.0, caster=True)
    for y in (-half - 0.6, half + 0.6):
        box(f'gate_jamb{y}', x - 1.5, x + 1.5, y - 0.6, y + 0.6, 0, h + 0.6, M_PLAIN, tile=2.0, caster=True)
    box('gate_lintel', x - 1.5, x + 1.5, -half - 1.2, half + 1.2, 5.8, h + 0.6, M_PLAIN, tile=2.0, caster=True, bottom=True)
    for i in range(9):
        y = -15.5 + i * 3.9
        if abs(y) < half + 1.5: continue
        box(f'citywall_merlon{i}', x - 1.2, x + 1.2, y - 0.7, y + 0.7, h, h + 1.1, M_ASHLAR2, tile=2.0, caster=True)

def castle():
    # raised ground with steps, a 14 m wall and a tall tower that keeps the last light
    for s_ in range(4):
        box(f'castle_step{s_}', 13.0 + s_ * 0.9, 34, -17, 17, 0, (s_ + 1) * 0.38, M_PLAIN, tile=2.5, caster=True)
    z0 = 1.52
    box('castle_wall', 19.0, 21.2, -15, 15, z0, z0 + 14.0, M_ASHLAR2, tile=6.0, caster=True)
    for i in range(16):
        y = -14.4 + i * 1.92
        box(f'castle_merlon{i}', 19.0, 19.9, y - 0.5, y + 0.5, z0 + 14.0, z0 + 15.2, M_ASHLAR2, tile=2.0, caster=True)
    quad_uv('castle_door', (18.97, -1.6, z0), (0, 1, 0), (0, 0, 1), 3.2, 5.0, DOOR, M_DOORS)
    box('castle_door_frame', 18.85, 19.05, -2.1, 2.1, z0 + 5.0, z0 + 5.6, M_PLAIN, tile=2.0)
    for i, y in enumerate((-9.0, 9.0)):
        quad_uv(f'castle_slit{i}', (18.97, y - 0.35, z0 + 8.5), (0, 1, 0), (0, 0, 1), 0.7, 1.8, SHUTTER, M_DOORS)
    tx0, tx1, ty0, ty1, th = 21.2, 28.2, 2.0, 9.0, 30.0
    box('tower', tx0, tx1, ty0, ty1, z0, th, M_ASHLAR2, tile=6.0, caster=True)
    box('tower_band', tx0 - 0.15, tx1 + 0.15, ty0 - 0.15, ty1 + 0.15, th - 1.2, th - 0.8, M_PLAIN, tile=2.0)
    for i in range(4):
        for side in range(4):
            if side < 2:
                xx = tx0 + 0.6 + i * 1.95; yy = ty0 if side == 0 else ty1 - 0.9
                box(f'tower_merlon{side}{i}', xx - 0.45, xx + 0.45, yy, yy + 0.9, th, th + 1.2, M_ASHLAR2, tile=2.0, caster=True)
            else:
                yy = ty0 + 0.6 + i * 1.95; xx = tx0 if side == 2 else tx1 - 0.9
                box(f'tower_merlon{side}{i}', xx, xx + 0.9, yy - 0.45, yy + 0.45, th, th + 1.2, M_ASHLAR2, tile=2.0, caster=True)
    for k, z in enumerate((z0 + 17.0, z0 + 22.5)):
        quad_uv(f'tower_slit{k}', (tx0 - 0.03, 5.15, z), (0, 1, 0), (0, 0, 1), 0.7, 1.8, SHUTTER, M_DOORS)

def scaffold():
    # the post on a low platform in front of the castle steps (S-050: the plaza doubles as the execution ground).
    # Original text: 「ついに磔台に昇り、釣り上げられてゆく友の両足に、齧りついた」 (ux/art-direction 4.1): the platform
    # is climbed from the square (steps on the west), someone standing on it reaches the feet of the person hoisted up
    # the post, and that person's head is well above the crowd.
    x0, x1, y0, y1, h = 9.6, 12.4, -1.5, 1.5, 1.2
    box('scaffold', x0, x1, y0, y1, 0, h, M_BARK, tile=1.5, caster=True)
    box('scaffold_kerb', x0 - 0.06, x1 + 0.06, y0 - 0.06, y1 + 0.06, 0, 0.25, M_PLAIN, tile=2.0)
    for k in range(3):                          # three 0.3 m steps, the platform is the fourth
        box(f'scaffold_step{k}', x0 - 0.35 * (4 - k), x0, -0.9, 0.9, 0, 0.3 * (k + 1), M_PLAIN, tile=2.0, caster=True)
    cyl('post', 11.0, 0.0, 0, 6.0, 0.17, 0.14, 8, M_BARK, caster=True)

def stoa():
    # back building
    box('stoa_back', -30, -21, -2, 16, 0, 6.4, M_ASHLAR2, tile=6.0, caster=True)
    box('stoa_back_cornice', -30.2, -20.8, -2.2, 16.2, 6.05, 6.4, M_PLAIN, tile=2.0)
    gable_roof('stoa_back', -30, -21, -2, 16, 6.4)
    facade_openings('stoa_back', '+x', -30, -21, -2, 16, 6.4, 2)
    # colonnade
    n = 7
    for i in range(n):
        y = -1.0 + i * (16.0 / (n - 1)) * (15.0 / 16.0)
        cyl(f'stoa_col{i}_base', -18.6, y, 0, 0.3, 0.48, 0.48, 12, M_PLAIN, caster=True)
        cyl(f'stoa_col{i}', -18.6, y, 0.3, 4.5, 0.34, 0.29, 14, M_PLAIN, caster=True)
        box(f'stoa_col{i}_cap', -19.05, -18.15, y - 0.45, y + 0.45, 4.5, 4.75, M_PLAIN, tile=2.0, caster=True)
    box('stoa_architrave', -19.2, -18.0, -1.6, 15.6, 4.75, 5.45, M_TRIM, tile=3.0, caster=True)
    box('stoa_ceiling', -21, -18.0, -1.6, 15.6, 5.45, 5.6, M_PLAIN, tile=3.0, caster=True, bottom=True)
    # lean-to roof
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    p = [(-21.0, -1.9, 6.25), (-17.6, -1.9, 5.6), (-17.6, 15.9, 5.6), (-21.0, 15.9, 6.25)]
    vs = [bm.verts.new(v) for v in p]
    f = bm.faces.new(vs)
    sl = math.dist(p[0], p[1])
    for l, uv in zip(f.loops, [(-1.9 / 3.5, sl / 3.5), (-1.9 / 3.5, 0), (15.9 / 3.5, 0), (15.9 / 3.5, sl / 3.5)]):
        l[uvl].uv = uv
    bm.normal_update()
    obj_from_bm('stoa_leanto', bm, [M_ROOF], 'arch', True)
    box('stoa_floor', -21, -17.9, -1.7, 15.7, 0, 0.22, M_PLAIN, tile=2.0)
    # benches
    for y in (2.5, 8.5):
        box(f'stoa_bench{y}', -20.6, -20.1, y, y + 2.2, 0.22, 0.65, M_PLAIN, tile=1.5, caster=True)

def temple():
    # podium with 3 steps
    for s in range(3):
        o = (2 - s) * 0.55
        box(f'temple_step{s}', -10.5 - o, 10.5 + o, 19 - o, 34 + o, s * 0.38, (s + 1) * 0.38, M_PLAIN, tile=2.5, caster=True)
    zb = 1.14
    xs = [-8.75 + i * 2.5 for i in range(8)]
    cols = [(x, 20.2) for x in xs] + [(x, 32.8) for x in xs]
    for y in [22.7, 25.2, 27.7, 30.2]:
        cols += [(-8.75, y), (8.75, y)]
    for i, (x, y) in enumerate(cols):
        cyl(f'temple_col{i}', x, y, zb, zb + 6.2, 0.62, 0.5, 16, M_PLAIN, tile=2.5, caster=True)
        box(f'temple_cap{i}', x - 0.72, x + 0.72, y - 0.72, y + 0.72, zb + 6.2, zb + 6.55, M_PLAIN, tile=2.0, caster=True)
    box('temple_cella', -6.2, 6.2, 22.5, 31.5, zb, zb + 6.55, M_ASHLAR2, tile=6.0, caster=True)
    quad_uv('temple_door', (-1.4, 22.47, zb), (1, 0, 0), (0, 0, 1), 2.8, 5.2, DOOR, M_DOORS)
    z0 = zb + 6.55
    box('temple_architrave', -9.6, 9.6, 19.4, 33.6, z0, z0 + 1.0, M_TRIM, tile=3.0, caster=True, bottom=True)
    box('temple_frieze', -9.75, 9.75, 19.25, 33.75, z0 + 1.0, z0 + 1.55, M_CORNICE, tile=4.0, caster=True)
    gable_roof('temple', -9.75, 9.75, 19.25, 33.75, z0 + 1.55, pitch_deg=14, over=0.5, ridge_axis='y')

FY = 7.5   # fountain centre: north of the gate-to-post line so the sunset corridor stays clear (art-direction 4.1)

def fountain():
    cyl('fountain_plat', 0, FY, 0, 0.18, 3.4, 3.4, 40, M_PLAIN, tile=2.0, caster=True)
    # basin ring
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    seg = 40; ro, ri, z0, z1 = 2.5, 2.15, 0.18, 0.92
    def ring(r, z):
        return [bm.verts.new((r * math.cos(2 * math.pi * i / seg), FY + r * math.sin(2 * math.pi * i / seg), z)) for i in range(seg)]
    ob, ot, it, ib = ring(ro, z0), ring(ro, z1), ring(ri, z1), ring(ri, z0 + 0.4)
    for A, B in [(ob, ot), (ot, it), (it, ib)]:
        for i in range(seg):
            j = (i + 1) % seg
            f = bm.faces.new((A[i], A[j], B[j], B[i]))
            for l in f.loops:
                co = l.vert.co
                ang = math.atan2(co.y - FY, co.x)
                l[uvl].uv = (ang * 2.4 / 2.0, co.z / 2.0 + (0.3 if B is it else 0))
    bm.normal_update()
    obj_from_bm('fountain_basin', bm, [M_PLAIN], 'arch', True)
    cyl('fountain_water', 0, FY, 0.5, 0.75, 2.16, 2.16, 40, M_WATER, cap=True)
    cyl('fountain_pillar', 0, FY, 0.5, 2.3, 0.32, 0.26, 16, M_PLAIN, caster=True)
    cyl('fountain_bowl', 0, FY, 2.3, 2.55, 0.35, 0.85, 20, M_PLAIN, caster=True)

def stall(name, x, y, rot_fab):
    for dx in (0, 3.0):
        for dy in (0, 2.2):
            cyl(f'{name}_post{dx}{dy}', x + dx, y + dy, 0, 2.5 - dx * 0.12, 0.06, 0.06, 6, M_BARK, caster=True)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    p = [(x - 0.3, y - 0.3, 2.55), (x + 3.3, y - 0.3, 2.15), (x + 3.3, y + 2.5, 2.15), (x - 0.3, y + 2.5, 2.55)]
    vs = [bm.verts.new(v) for v in p]
    f = bm.faces.new(vs)
    for l, uv in zip(f.loops, [(0, 0), (1, 0), (1, 0.8), (0, 0.8)]):
        l[uvl].uv = uv
    bm.normal_update()
    obj_from_bm(f'{name}_awning', bm, [rot_fab], 'arch', True)
    box(f'{name}_table', x + 0.1, x + 2.9, y + 0.2, y + 1.2, 0.0, 0.85, M_BARK, tile=1.5, caster=True)

def workshop():
    # Selinuntius's stonemason's yard (place.stonemason-workshop, scenes/syracuse-square/layout.json): a walled yard in
    # the south-west corner in front of his house (building S1), an open shed, blocks and a half-dressed column drum.
    # The gate leaf is its own node in the 'dyn' group (not baked) so the page can swing it shut when the place is
    # closed (api-contract 2.3 places[].enabled = false).
    x0, x1, y0, y1 = -18.0, -6.5, -23.0, -16.35
    t, h = 0.5, 1.9
    g0, g1 = -12.6, -10.6                       # gateway in the north wall
    box('yard_wall_nw', x0 - t / 2, g0 - 0.3, y1 - t / 2, y1 + t / 2, 0, h, M_ASHLAR, tile=3.0, caster=True)
    box('yard_wall_ne', g1 + 0.3, x1 + t / 2, y1 - t / 2, y1 + t / 2, 0, h, M_ASHLAR, tile=3.0, caster=True)
    box('yard_wall_w', x0 - t / 2, x0 + t / 2, y0, y1 - t / 2, 0, h, M_ASHLAR, tile=3.0, caster=True)
    box('yard_wall_e', x1 - t / 2, x1 + t / 2, y0, y1 - t / 2, 0, h, M_ASHLAR, tile=3.0, caster=True)
    for i, gx in enumerate((g0 - 0.3, g1)):
        box(f'yard_gatepost{i}', gx, gx + 0.3, y1 - 0.32, y1 + 0.32, 0, 2.45, M_PLAIN, tile=2.0, caster=True)
    # gate leaf, open: hinged on the west post, swung into the yard (closed = rotate -90° about the hinge)
    leaf = box('workshop_gate', g0, g0 + 0.08, y1 - 2.0, y1, 0.06, 1.86, M_BARK, group='dyn', tile=1.2, caster=True)
    hinge = Vector((g0, y1, 0.0))
    leaf.data.transform(Matrix.Translation(-hinge)); leaf.location = hinge
    # shed against the house: two posts and a lean-to roof
    for i, px in enumerate((-17.4, -13.1)):
        cyl(f'shed_post{i}', px, -20.75, 0, 2.45, 0.09, 0.08, 8, M_BARK, caster=True)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    p = [(-17.7, -22.95, 3.05), (-12.8, -22.95, 3.05), (-12.8, -20.5, 2.42), (-17.7, -20.5, 2.42)]
    f = bm.faces.new([bm.verts.new(v) for v in p])
    sl = math.dist(p[1], p[2])
    for l, uv in zip(f.loops, [(0, sl / 3.5), (4.9 / 3.5, sl / 3.5), (4.9 / 3.5, 0), (0, 0)]):
        l[uvl].uv = uv
    bm.normal_update()
    obj_from_bm('shed_roof', bm, [M_ROOF], 'arch', True)
    # rough blocks under the shed and in the yard, one stacked; a column drum being dressed; the bench
    for i, (bx, by, sx, sy, sz, z0) in enumerate([(-16.6, -21.9, 1.4, 0.9, 0.8, 0), (-16.5, -21.85, 1.0, 0.7, 0.55, 0.8),
                                                   (-14.9, -22.0, 1.1, 0.8, 0.7, 0), (-16.2, -18.6, 0.9, 0.9, 0.6, 0),
                                                   (-7.9, -18.3, 0.8, 0.6, 0.45, 0)]):
        box(f'yard_block{i}', bx - sx / 2, bx + sx / 2, by - sy / 2, by + sy / 2, z0, z0 + sz, M_ASHLAR2, tile=1.2, caster=True)
    cyl('yard_drum', -13.2, -19.9, 0, 0.9, 0.55, 0.55, 18, M_PLAIN, caster=True)
    cyl('yard_drum2', -11.9, -21.6, 0, 0.62, 0.5, 0.5, 18, M_PLAIN, caster=True)
    box('yard_bench', -10.0, -8.0, -21.9, -21.2, 0, 0.85, M_BARK, tile=1.5, caster=True)
    box('yard_bench_stone', -9.6, -8.9, -21.75, -21.3, 0.85, 1.12, M_PLAIN, tile=1.0)
    for i, (cx, cy) in enumerate([(-9.6, -18.9), (-9.1, -18.4), (-8.6, -19.2), (-10.2, -18.3)]):
        box(f'yard_chip{i}', cx - 0.18, cx + 0.18, cy - 0.14, cy + 0.14, 0, 0.12, M_PLAIN, tile=1.0)

def amphora(name, x, y, s=1.0):
    prof = [(0.0, 0), (0.12, 0.0), (0.2, 0.08), (0.27, 0.3), (0.26, 0.5), (0.17, 0.68), (0.08, 0.74), (0.07, 0.86), (0.1, 0.9), (0.0, 0.9)]
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    seg = 12
    rings = [[bm.verts.new((x + r * s * math.cos(2 * math.pi * i / seg), y + r * s * math.sin(2 * math.pi * i / seg), z * s)) for i in range(seg)] for r, z in prof]
    for k in range(len(rings) - 1):
        for i in range(seg):
            j = (i + 1) % seg
            try:
                f = bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
                for l, uv in zip(f.loops, [(i / seg, k / 9), ((i + 1) / seg, k / 9), ((i + 1) / seg, (k + 1) / 9), (i / seg, (k + 1) / 9)]):
                    l[uvl].uv = uv
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.normal_update()
    obj_from_bm(name, bm, [M_CLAY], 'arch', False)

def blob_tree(name, x, y, h, r, m_leaf, cypress=False, group='arch'):
    cyl(name + '_trunk', x, y, 0, h * (0.25 if cypress else 0.45), 0.12 if cypress else 0.22, 0.08 if cypress else 0.15, 7, M_BARK, group=group, caster=True)
    bm = bmesh.new()
    if cypress:
        bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=12, radius=1.0)
        for v in bm.verts:
            t = (v.co.z + 1) / 2
            w = r * (0.55 + 0.6 * math.sin(math.pi * min(1, t * 1.15))) * (1 - 0.65 * t)
            n = noise.noise(Vector((v.co.x * 2 + x, v.co.y * 2 + y, v.co.z * 3))) * 0.25
            v.co = Vector((x + v.co.x * w * (1 + n), y + v.co.y * w * (1 + n), h * 0.12 + t * h * 0.95))
    else:
        for k in range(5):
            cx = x + random.uniform(-1, 1) * r * 0.6; cy = y + random.uniform(-1, 1) * r * 0.6
            cz = h * 0.55 + random.uniform(0, 1) * h * 0.3
            rr = r * random.uniform(0.45, 0.7)
            g = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rr)
            for v in g['verts']:
                n = noise.noise(v.co * 1.7 + Vector((x, y, k))) * 0.35
                v.co = Vector((cx + v.co.x * (1 + n), cy + v.co.y * (1 + n), cz + v.co.z * 0.7 * (1 + n)))
    bm.normal_update()
    box_uv_bm(bm, 1.6)
    obj_from_bm(name + '_leaves', bm, [m_leaf], group, True)

def hills():
    bm = bmesh.new()
    res = 64; R0, R1 = 110, 260
    grid = []
    for j in range(res + 1):
        row = []
        for i in range(res + 1):
            x = -R1 + 2 * R1 * i / res; y = -R1 + 2 * R1 * j / res
            d = math.hypot(x, y)
            ang = math.atan2(y, x)
            west = max(0.0, math.cos(ang - math.pi))  # 1 toward the sun (−X): the Iblei hills, kept low in angle
            east = max(0.0, math.cos(ang))            # toward the sea behind the castle: flat
            hgt = 0.0
            if d > R0:
                k = min(1.0, (d - R0) / 70)
                hgt = k * (14 + 26 * (noise.noise(Vector((x / 90, y / 90, 0.3))) * 0.5 + 0.5) + 10 * noise.noise(Vector((x / 30, y / 30, 1.7)))) * (1 - 0.9 * east ** 2)
                if west > 0.6:
                    hgt = min(hgt, d * 0.022)
            row.append(bm.verts.new((x, y, hgt - 0.6)))
        grid.append(row)
    for j in range(res):
        for i in range(res):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    bm.normal_update(); box_uv_bm(bm, 25.0)
    obj_from_bm('hills', bm, [M_HILL], 'far')

def distant_city():
    random.seed(11)
    k = 0
    for _ in range(140):
        ang = random.uniform(0, 2 * math.pi)
        if math.cos(ang - math.pi) > 0.55:   # keep the sun side open (sea)
            continue
        d = random.uniform(42, 95)
        x, y = d * math.cos(ang), 2 + d * math.sin(ang)
        if -36 < x < 36 and -34 < y < 40:
            continue
        w, dd = random.uniform(6, 12), random.uniform(6, 11)
        h = random.uniform(5, 10)
        box(f'city{k}', x - w / 2, x + w / 2, y - dd / 2, y + dd / 2, -0.5, h, M_PLASTER if k % 3 else M_ASHLAR2, group='far', tile=6.0)
        gable_roof_far(f'city{k}', x - w / 2, x + w / 2, y - dd / 2, y + dd / 2, h)
        k += 1

def gable_roof_far(name, x0, x1, y0, y1, z):
    bm = bmesh.new()
    tp = math.tan(math.radians(21)); o = 0.3
    X0, X1, Y0, Y1 = x0 - o, x1 + o, y0 - o, y1 + o
    ym = (Y0 + Y1) / 2; rz = z + (Y1 - Y0) / 2 * tp
    a, b, c, d = [bm.verts.new(v) for v in [(X0, Y0, z), (X1, Y0, z), (X1, ym, rz), (X0, ym, rz)]]
    e, f, g, h = [bm.verts.new(v) for v in [(X1, Y1, z), (X0, Y1, z), (X0, ym, rz), (X1, ym, rz)]]
    bm.faces.new((a, b, c, d)); bm.faces.new((e, f, g, h))
    bm.faces.new((a, d, f)); bm.faces.new((b, e, c))
    bm.normal_update(); box_uv_bm(bm, 3.5)
    obj_from_bm(name + '_roof', bm, [M_ROOF], 'far')

# ---------------------------------------------------------------- compose
ground()
# west: two 8 m blocks either side of the gate street (y in [-3, 3]) and the city gate at x = -34
building('WS', -31, -18, -16, -3, 8, ['+x', '+y'], warm=True)
building('WN', -31, -18, 3, 16, 8, ['+x', '-y'])
city_gate()
building('NW', -26, -12, 20.5, 30, 9, ['-y', '+x'])
temple()
building('NE', 12.5, 25, 20, 31, 10, ['-y', '-x'], warm=True)
castle()
scaffold()
building('S1', -18, -6.5, -28, -23, 9, ['+y'])   # the stonemason's house; his yard is in front (workshop())
building('S2', -3.5, 6, -26, -16, 7.5, ['+y'], warm=True)   # the old man's house; its door (x ≈ 3.6) faces the square
building('S3', 8.5, 18, -28, -16, 10, ['+y'])
fountain()
workshop()
stall('stallA', -8.0, -13.0, M_FAB_R)
stall('stallB', -2.6, -13.0, M_FAB_B)
for i, (x, y, s) in enumerate([(-4.4, -13.3, 1.0), (-4.0, -12.7, 0.85), (1.2, -13.4, 1.1), (1.7, -12.8, 0.9), (-9.0, -11.0, 1.0)]):
    amphora(f'amph{i}', x, y, s)
for i, (x, y, h) in enumerate([(-14, 36, 13), (-17, 38, 11), (14, 35, 12), (17, 37.5, 14), (30, 26, 12), (-33, 24, 10), (-36, -22, 11), (-2, -33, 11)]):
    blob_tree(f'cypress{i}', x, y, h, 1.25, M_CYPRESS, cypress=True, group='far')
hills()
distant_city()

# rotate everything (local −X is the gate street = azimuth 294°; the sky is generated to match)
ROT = math.radians(144.0)
R = Matrix.Rotation(ROT, 4, 'Z')
for o in scene.objects:
    o.data.transform(R)
    o.location = R @ o.location   # only the gate leaf has an origin away from 0

bpy.ops.wm.save_as_mainfile(filepath=f'{OUT}/plaza_raw.blend')
counts = {}
for o in scene.objects:
    g = o.users_collection[0].name
    counts.setdefault(g, [0, 0])
    counts[g][0] += 1
    counts[g][1] += sum(len(p.vertices) - 2 for p in o.data.polygons)
print('GROUPS', counts)
