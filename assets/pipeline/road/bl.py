# Blender helpers for the road stops (F-10). The same materials and mesh helpers as ../plaza/build_plaza.py, which
# runs its whole scene on import, so they are kept here for the road scripts rather than imported from there.
# Groups as the plaza's bake.py expects them: 'ground' (one object named ground, planar lightmap), 'arch' (baked,
# objects with caster = 1 also go into the shadow proxy), 'far' (not baked), 'dyn' (own nodes, hidden in the bake).
import bpy, bmesh, math, os, random
from mathutils import Vector, Matrix, noise

T = None    # texture dir, set by setup()
scene = None
_imgs, MATS, COLL = {}, {}, {}


def setup(tex_dir):
    global T, scene
    T = tex_dir
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    return scene


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
    return mat(name, tex_exists(f'{base_key or key}_base'), tex_exists(f'{key}_nrm'), tex_exists(f'{key}_mr'), **kw)


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


def box_uv_bm(bm, tile, uvname='UVMap'):
    uvl = bm.loops.layers.uv.get(uvname) or bm.loops.layers.uv.new(uvname)
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            co = l.vert.co
            if ax == 0:
                u, v = (co.y if n.x > 0 else -co.y), co.z
            elif ax == 1:
                u, v = (-co.x if n.y > 0 else co.x), co.z
            else:
                u, v = co.x, co.y
            l[uvl].uv = (u / tile, v / tile)


def box(name, x0, x1, y0, y1, z0, z1, m, group='arch', tile=4.0, caster=False, bottom=False, xform=None):
    """axis-aligned box; xform (a Matrix) is applied to the vertices before the UVs, so a tilted box keeps its grain"""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z)) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    def q(a, b, c, d):
        bm.faces.new((vs[a], vs[b], vs[c], vs[d]))
    q(0, 2, 3, 1) if bottom else None
    q(4, 5, 7, 6); q(0, 1, 5, 4); q(2, 6, 7, 3); q(0, 4, 6, 2); q(1, 3, 7, 5)
    if xform is not None:
        bmesh.ops.transform(bm, matrix=xform, verts=bm.verts)
    bm.normal_update()
    box_uv_bm(bm, tile)
    return obj_from_bm(name, bm, [m], group, caster)


def cyl(name, cx, cy, z0, z1, r0, r1=None, seg=16, m=None, group='arch', tile=2.0, caster=False, cap=True, xform=None,
        cap_mat=None):
    """upright cylinder; xform tilts it (about its own base when built with Matrix.Translation around it);
    cap_mat: the top face gets its own material (a fresh break on a broken pile)"""
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
        f.material_index = 1 if cap_mat else 0
        for l in f.loops:
            l[uvl].uv = (l.vert.co.x / tile, l.vert.co.y / tile)
    if xform is not None:
        bmesh.ops.transform(bm, matrix=xform, verts=bm.verts)
    bm.normal_update()
    return obj_from_bm(name, bm, [m] + ([cap_mat] if cap_mat else []), group, caster)


def rod(name, a, b, r, m, group='arch', seg=7, caster=False):
    """a cylinder from point a to point b (branches, rope ends, rails)"""
    a, b = Vector(a), Vector(b)
    d = b - a
    q = d.to_track_quat('Z', 'Y')
    xf = Matrix.Translation(a) @ q.to_matrix().to_4x4()
    return cyl(name, 0, 0, 0, d.length, r, r * 0.8, seg, m, group, tile=1.0, caster=caster, cap=False, xform=xf)


def rock(name, x, y, z, r, m, squash=0.6, seed=0, group='arch', caster=True, subdiv=2):
    """a limestone outcrop: a lumpy icosahedron, flattened and partly sunk into the ground"""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    for v in bm.verts:
        n = noise.noise(v.co * 1.3 + Vector((seed, seed * 0.7, 3.1))) * 0.35 + noise.noise(v.co * 3.1 + Vector((seed, 1, 0))) * 0.12
        v.co = Vector((x + v.co.x * r * (1 + n), y + v.co.y * r * 0.8 * (1 + n), z + v.co.z * r * squash * (1 + n)))
    bm.normal_update()
    box_uv_bm(bm, 1.5)
    return obj_from_bm(name, bm, [m], group, caster)


def tree(name, x, y, h, r, m_leaf, m_bark, shape='round', z=0.0, group='arch', lean=(0.0, 0.0)):
    """white poplar ('spread': broad, ragged, see-through crown on a leaning trunk; not the columnar Lombardy poplar,
    a later cultivar), holm oak ('round'), willow ('weep': wide, hanging, leaning trunk)"""
    th = h * (0.33 if shape == 'spread' else 0.45)   # white poplar: the crown starts in the trunk's lower third
    crowns = []   # (centre, radius, z scale) of every blob, for the leaf cards
    tx, ty = x + lean[0] * th, y + lean[1] * th
    rod(name + '_trunk', (x, y, z - 0.3), (tx, ty, z + th), 0.22, m_bark, group, caster=True)
    bm = bmesh.new()
    if shape == 'spread':
        # scattered blobs with gaps between them, from mid-height up; two main limbs fork off the trunk.
        # Seeded from the position (str hashes change from one process to the next)
        rr = random.Random(int(round(x * 100)) * 7919 + int(round(y * 100)))
        for i, a in enumerate((rr.uniform(0, math.pi), None)):
            a = a if a is not None else a_prev + math.pi * rr.uniform(0.7, 1.1)
            a_prev = a
            rod(f'{name}_limb{i}', (tx, ty, z + th - 0.2),
                (tx + math.cos(a) * r * 0.4, ty + math.sin(a) * r * 0.4, z + h * 0.58), 0.12, m_bark, group, caster=True)
        for i in range(7):
            a = 2 * math.pi * i / 7 + rr.uniform(-0.35, 0.35)
            d = r * rr.uniform(0.15, 0.7)
            cx, cy, cz = tx + math.cos(a) * d, ty + math.sin(a) * d, z + h * rr.uniform(0.36, 0.9)
            rad = r * rr.uniform(0.34, 0.48)
            crowns.append((Vector((cx, cy, cz)), rad, 0.85))
            g = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rad)
            for v in g['verts']:
                n = noise.noise(v.co * 1.9 + Vector((x, y, i))) * 0.35
                v.co = Vector((cx + v.co.x * (1 + n), cy + v.co.y * (1 + n), cz + v.co.z * 0.85 * (1 + n)))
    elif shape == 'round':
        # holm oak: one round, dense mass (not the flat-topped clumps of a stone pine): a core and lobes round it,
        # bulging up as much as out
        rr = random.Random(int(round(x * 100)) * 7919 + int(round(y * 100)))
        cz0 = z + h * 0.62
        lobes = [(0.0, 0.0, 0.0, 0.72)] + [(math.cos(2 * math.pi * i / 6 + 0.4 * i), math.sin(2 * math.pi * i / 6 + 0.4 * i),
                                             (0.25 if i % 2 else -0.15), 0.5) for i in range(6)]
        for i, (ux, uy, uz, s_) in enumerate(lobes):
            cx, cy, cz = tx + ux * r * 0.45, ty + uy * r * 0.45, cz0 + uz * h * 0.25
            # the core smooth, the lobes coarser (they stand 28 m off and more; the pack's bytes are tight)
            rad = r * s_ * rr.uniform(0.9, 1.1)
            crowns.append((Vector((cx, cy, cz)), rad, 0.95))
            g = bmesh.ops.create_icosphere(bm, subdivisions=2 if i == 0 else 1, radius=rad)
            for v in g['verts']:
                n = noise.noise(v.co * 1.7 + Vector((x, y, i))) * 0.22
                v.co = Vector((cx + v.co.x * (1 + n), cy + v.co.y * (1 + n), cz + v.co.z * 0.95 * (1 + n)))
    else:
        k = 8 if shape == 'weep' else 5
        for i in range(k):
            a = 2 * math.pi * i / k + noise.noise(Vector((x, y, i))) * 0.6
            rr = r * (0.45 if shape == 'weep' else 0.62)
            cx, cy = tx + math.cos(a) * r * 0.5, ty + math.sin(a) * r * 0.5
            cz = z + (h * 0.62 if shape == 'weep' else h * 0.66) + noise.noise(Vector((i, x, y))) * h * 0.08
            g = bmesh.ops.create_icosphere(bm, subdivisions=2 if shape == 'weep' else 1, radius=rr)
            for v in g['verts']:
                n = noise.noise(v.co * 1.7 + Vector((x, y, i))) * 0.3
                sz = 1.35 if shape == 'weep' else 0.75
                v.co = Vector((cx + v.co.x * (1 + n), cy + v.co.y * (1 + n), cz + v.co.z * sz * (1 + n)))
        if shape == 'weep':   # the hanging curtain: pull the lower half of every blob down and outwards
            for v in bm.verts:
                if v.co.z < z + h * 0.62:
                    d = Vector((v.co.x - tx, v.co.y - ty, 0))
                    v.co += d * 0.15 + Vector((0, 0, -(z + h * 0.62 - v.co.z) * 0.6))
    for f in bm.faces:   # smooth: the faceted blobs read as low-poly rocks, not foliage
        f.smooth = True
    bm.normal_update()
    box_uv_bm(bm, 1.6)
    o = obj_from_bm(name + '_leaves', bm, [m_leaf], group, True)
    if crowns:
        rr = random.Random(int(round(x * 100)) * 104729 + int(round(y * 100)))
        leaf_cards(name + '_cards', crowns, 9 if shape == 'spread' else 7, 1.5 if shape == 'spread' else 1.0,
                   m_leaf, group, rr)
    return o


def leaf_cards(name, crowns, per, size, m, group, rr, droop=False, uv_tile=1.6):
    """leaf cards over a crown's blobs (UX round 2: the blobs alone read as low-poly balls): small hexagons of the
    alpha-tested leaf texture (a random piece of its 1.6 m tile, the blobs' scale), standing out of the blob surfaces so
    the crown's edge is ragged and lets the sky through. Their normals point out of the crown (not across the card), so
    a crown is lit as one mass. Not shadow casters: the blobs cast the crown's shadow. droop: hanging, facing out
    sideways (the willow)"""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    normals = []
    up = Vector((0, 0, 1))
    for c, rad, sz in crowns:
        for _ in range(per):
            d = Vector((rr.gauss(0, 1), rr.gauss(0, 1), rr.gauss(0, 1) + (0.0 if droop else 0.35))).normalized()
            p = c + Vector((d.x, d.y, d.z * sz)) * rad * rr.uniform(0.7, 1.05)
            if droop:
                nrm = Vector((d.x, d.y, 0.0)).normalized() if d.xy.length > 1e-3 else Vector((1, 0, 0))
                t = nrm.cross(up).normalized()
                b = -up
                a = rr.uniform(-0.35, 0.35)
            else:
                nrm = (d + Vector((rr.gauss(0, 0.5), rr.gauss(0, 0.5), rr.gauss(0, 0.5)))).normalized()
                t = nrm.cross(up if abs(nrm.z) < 0.9 else Vector((1, 0, 0))).normalized()
                b = nrm.cross(t)
                a = rr.uniform(0, 2 * math.pi)
            t, b = t * math.cos(a) + b * math.sin(a), b * math.cos(a) - t * math.sin(a)
            half = size * 0.5 * rr.uniform(0.8, 1.2)
            u0, v0 = rr.random(), rr.random()
            out = (Vector(((p - c).x, (p - c).y, (p - c).z / sz)).normalized() + up * 0.3).normalized()
            vs, uvs = [], []
            for k in range(6):
                q = 2 * math.pi * (k + 0.5) / 6
                lx, ly = math.cos(q) * half, math.sin(q) * half * (1.4 if droop else 1.0)
                vs.append(bm.verts.new(p + t * lx + b * ly))
                uvs.append((u0 + lx / uv_tile, v0 + ly / uv_tile))
                normals.append(out)
            f = bm.faces.new(vs)
            for l, uv in zip(f.loops, uvs):
                l[uvl].uv = uv
    bm.normal_update()
    o = obj_from_bm(name, bm, [m], group, False)
    o.data.normals_split_custom_set_from_vertices(normals)
    return o


def gable(name, x0, x1, y0, y1, z, m_roof, m_wall, pitch_deg=35, over=0.35, group='arch'):
    """a pitched roof with its ridge along y, and the two triangular gable walls"""
    tp = math.tan(math.radians(pitch_deg))
    X0, X1, Y0, Y1 = x0 - over, x1 + over, y0 - over, y1 + over
    xm = (X0 + X1) / 2; rz = z + (X1 - X0) / 2 * tp
    bm = bmesh.new()
    a, b, c, d = [bm.verts.new(v) for v in [(X1, Y0, z), (X1, Y1, z), (xm, Y1, rz), (xm, Y0, rz)]]
    e, f, g, h = [bm.verts.new(v) for v in [(X0, Y1, z), (X0, Y0, z), (xm, Y0, rz), (xm, Y1, rz)]]
    bm.faces.new((a, b, c, d)); bm.faces.new((e, f, g, h))
    bm.normal_update(); box_uv_bm(bm, 2.0)
    obj_from_bm(name + '_roof', bm, [m_roof], group, True)
    bm = bmesh.new()
    zr = z + (x1 - x0) / 2 * tp
    for yy, flip in [(y0, False), (y1, True)]:
        vs = [bm.verts.new(v) for v in [(x0, yy, z), (x1, yy, z), ((x0 + x1) / 2, yy, zr)]]
        bm.faces.new(vs[::-1] if flip else vs)
    bm.normal_update(); box_uv_bm(bm, 3.0)
    obj_from_bm(name + '_gable', bm, [m_wall], group, True)


def heightfield(name, xs, ys, hfun, matfun, mats, group, skip=None, tile=3.0, tris=False):
    """a grid on the lines xs × ys; hfun(x, y) -> z; matfun(cx, cy, cz) -> index into mats for each quad;
    skip(cx, cy) drops a quad (the far ring leaves a hole where the near ground is); tris splits every quad on its
    (x0, y0)-(x1, y1) diagonal, so grid_height() gives the exact surface (something laid on it, the far road)"""
    bm = bmesh.new()
    V = [[bm.verts.new((x, y, hfun(x, y))) for x in xs] for y in ys]
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if skip and skip(cx, cy):
                continue
            q = (V[j][i], V[j][i + 1], V[j + 1][i + 1], V[j + 1][i])
            m = matfun(cx, cy, sum(v.co.z for v in q) / 4)
            for f in ((bm.faces.new((q[0], q[1], q[2])), bm.faces.new((q[0], q[2], q[3]))) if tris else (bm.faces.new(q),)):
                f.material_index = m
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.normal_update()
    box_uv_bm(bm, tile)
    return obj_from_bm(name, bm, mats, group)


def grid_height(xs, ys, hfun, x, y):
    """the height of heightfield(..., tris=True) at (x, y): the plane of the triangle under the point"""
    import bisect
    i = min(max(bisect.bisect_right(xs, x) - 1, 0), len(xs) - 2)
    j = min(max(bisect.bisect_right(ys, y) - 1, 0), len(ys) - 2)
    u = (x - xs[i]) / (xs[i + 1] - xs[i]); v = (y - ys[j]) / (ys[j + 1] - ys[j])
    z00, z10, z11, z01 = hfun(xs[i], ys[j]), hfun(xs[i + 1], ys[j]), hfun(xs[i + 1], ys[j + 1]), hfun(xs[i], ys[j + 1])
    if u >= v:   # triangle (00, 10, 11)
        return z00 + u * (z10 - z00) + v * (z11 - z10)
    return z00 + v * (z01 - z00) + u * (z11 - z01)   # triangle (00, 11, 01)


def lines(*spans, extra=()):
    """grid lines: spans of (start, stop, step), plus extra lines, sorted and de-duplicated to 1 cm"""
    out = set()
    for a, b, s in spans:
        n = int(round((b - a) / s))
        out.update(round(a + k * (b - a) / n, 2) for k in range(n + 1))
    out.update(round(v, 2) for v in extra)
    return sorted(out)


def save(path):
    bpy.ops.wm.save_as_mainfile(filepath=path)
    counts = {}
    for o in scene.objects:
        g = o.users_collection[0].name
        counts.setdefault(g, [0, 0])
        counts[g][0] += 1
        counts[g][1] += sum(len(p.vertices) - 2 for p in o.data.polygons)
    print('GROUPS', counts)
