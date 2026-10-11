# The village's other light (F-11, village.md 5): the light sub-packs village-light-<set>.
#   relight.py -- <set> <final|draft>      set = sunset | night | rain
# Bakes the ground and arch lightmaps of the baked village again for that light, on the same lightmap UVs (it opens
# <stem>_baked.blend, which bake.py saved after making them), into <work>/light-<set>/. Only the indirect light: the
# AO does not change with the light (the page keeps the village pack's), and the sun is drawn live as for the day.
# The village stays as baked: its walls and roofs shade, the instanced copies occlude. (The inside of Melos's house is
# its own sub-pack, ./interior/.)
# Writes lm_<mesh>_indirect.png (sRGB, baked / K; three: lightMapIntensity = PI * K, as encode.py) and lm_meta.json.
import bpy, math, sys, os, json, time
import numpy as np
from mathutils import Vector, Matrix
from PIL import Image, ImageFilter
argv = sys.argv[sys.argv.index('--') + 1:]
SET, Q = argv[0], (argv[1] if len(argv) > 1 else 'final')
OUT = os.environ['PLAZA_OUT']
STEM = os.environ['SCENE_STEM']
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'plaza'))
from sunpos import sun_local

# ---------------------------------------------------------------- the lights (village.md 5.1〜5.3)
# sky: 'sunset' = sky.py at 18:30 (build.sh draws it into
# light-sunset/), or dome = (linear rgb, horizontal irradiance, 'overcast' | 'even'): a sky without a sun (the CIE
# overcast sky is three times brighter at the zenith than at the horizon). sun: (irradiance, rgb), the plaza's units
# (bake.py: 6 for a clear sun). lamps: (plan x, y, height above the floor, watts, rgb, radius).
LAMP = (1.0, 0.6, 0.3)         # an oil lamp, about 1900 K in the page's sRGB
HEARTH = (1.0, 0.5, 0.22)
SETS = {
    'sunset': dict(minute=1110, sky='sunset', sun=(6.0, (1.0, 0.58, 0.32))),
    # day 1 night under the groom's arbour: stars and one lamp hanging over the table (beat.10)
    'night': dict(minute=1290, dome=((0.3, 0.4, 0.75), 0.004, 'even'), lamps=[(-25.8, 9.5, 1.9, 6.0, LAMP, 0.04)]),
    # day 2 from 12:20: the low even grey of the storm; the page dims it for the rainy night and day 3's dawn
    'rain': dict(minute=780, dome=((0.62, 0.66, 0.72), 0.7, 'overcast')),
}
RES = 1024 if Q == 'final' else 512
SPP = {'full': 96, 'sundirect': 24} if Q == 'final' else {'full': 8, 'sundirect': 4}

bpy.ops.wm.open_mainfile(filepath=f'{OUT}/{STEM}_baked.blend')
scene = bpy.context.scene
vl = bpy.context.view_layer
ROT = Matrix.Rotation(math.radians(float(os.environ.get('SCENE_ROT_DEG', '0'))), 4, 'Z')
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'
for o in [o for o in scene.objects if o.type == 'LIGHT']:
    bpy.data.objects.remove(o)
world = bpy.data.worlds.new('World'); scene.world = world; world.use_nodes = True
WN, WL = world.node_tree.nodes, world.node_tree.links
bg = WN['Background']
SUN = []
LAMPS = []


def floor_z(x, y):
    """the height of the baked ground at plan (x, y)"""
    g = bpy.data.objects['ground']
    hit, loc, *_ = g.ray_cast(g.matrix_world.inverted() @ Vector((x, y, 50.0)), Vector((0, 0, -1)))
    assert hit, f'no ground at {x}, {y}'
    return (g.matrix_world @ loc).z


def set_light(L, dest):
    """the world, the sun and the lamps of one light; records what the page needs in dest"""
    for o in SUN + LAMPS:
        bpy.data.objects.remove(o)
    SUN.clear(); LAMPS.clear()
    for n in [n for n in WN if n.name not in ('Background', 'World Output')]:
        WN.remove(n)
    if 'sky' in L:
        env = WN.new('ShaderNodeTexEnvironment')
        env.image = bpy.data.images.load(f'{OUT}/light-{L["sky"]}/sky_sunset.hdr')
        WL.new(env.outputs['Color'], bg.inputs['Color'])
        dest['sky'] = {'kind': 'clear', 'minute': L['minute']}
    else:
        rgb, e, kind = L['dome']
        # radiance at the zenith Lz for a horizontal irradiance e: even, e = pi Lz; CIE overcast, L = Lz (1 + 2 sin h) / 3,
        # e = 7 pi Lz / 9
        lz = e / math.pi if kind == 'even' else e * 9 / (7 * math.pi)
        tc = WN.new('ShaderNodeTexCoord'); sep = WN.new('ShaderNodeSeparateXYZ')
        WL.new(tc.outputs['Generated'], sep.inputs['Vector'])
        up = WN.new('ShaderNodeMath'); up.operation = 'MAXIMUM'; up.inputs[1].default_value = 0.0
        WL.new(sep.outputs['Z'], up.inputs[0])
        k = WN.new('ShaderNodeMath'); k.operation = 'MULTIPLY_ADD'
        k.inputs[1].default_value = (2 / 3 if kind == 'overcast' else 0.0) * lz
        k.inputs[2].default_value = (1 / 3 if kind == 'overcast' else 1.0) * lz
        WL.new(up.outputs['Value'], k.inputs[0])
        mix = WN.new('ShaderNodeVectorMath'); mix.operation = 'SCALE'
        mix.inputs[0].default_value = rgb
        WL.new(k.outputs['Value'], mix.inputs['Scale'])
        WL.new(mix.outputs['Vector'], bg.inputs['Color'])
        dest['sky'] = {'kind': kind, 'rgb': list(rgb), 'irradiance': e}
    bg.inputs['Strength'].default_value = 1.0
    if 'sun' in L:
        sl, el, az = sun_local(L['minute'])
        sd = (ROT @ sl).normalized()
        ld = bpy.data.lights.new('Sun', 'SUN'); ld.energy = L['sun'][0]; ld.color = L['sun'][1]; ld.angle = math.radians(1.2)
        o = bpy.data.objects.new('Sun', ld); scene.collection.objects.link(o)
        o.rotation_euler = (-sd).to_track_quat('-Z', 'Y').to_euler()
        SUN.append(o)
        dest['sun'] = {'intensity': L['sun'][0], 'rgb': list(L['sun'][1]), 'elevationDeg': round(el, 2), 'azimuthDeg': round(az, 1)}
    else:
        dest['sun'] = None
    dest['lamps'] = []
    for i, (x, y, h, w, rgb, r) in enumerate(L.get('lamps', ())):
        ld = bpy.data.lights.new(f'lamp{i}', 'POINT'); ld.energy = w; ld.color = rgb; ld.shadow_soft_size = r
        o = bpy.data.objects.new(f'lamp{i}', ld); scene.collection.objects.link(o)
        z = floor_z(x, y) + h
        o.location = (x, y, z)
        LAMPS.append(o)
        # where the page puts a dynamic light for the characters (glTF frame: x, height, -y)
        dest['lamps'].append({'pos': [round(x, 3), round(z, 3), round(-y, 3)], 'rgb': list(rgb), 'watts': w})
    dest['bakeMinute'] = L['minute']


def select_only(objs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    vl.objects.active = objs[0]


def bake(o, kind, res, path):
    """kind: full (all light) or sundirect (the sun's direct light only)"""
    im = bpy.data.images.new(f'{o.name}_{kind}', res, res, float_buffer=True)
    for m in o.data.materials:
        nt = m.node_tree
        n = nt.nodes.get('__bake__') or nt.nodes.new('ShaderNodeTexImage')
        n.name = '__bake__'; n.image = im
        for x in nt.nodes:
            x.select = False
        n.select = True; nt.nodes.active = n
    select_only([o])
    scene.cycles.samples = SPP[kind]
    lamps_on = [l.data.energy for l in LAMPS]
    t = time.time()
    if kind == 'full':
        bpy.ops.object.bake(type='DIFFUSE', pass_filter={'DIRECT', 'INDIRECT'}, uv_layer='lightmap', use_clear=True, margin=16)
    else:
        bg.inputs['Strength'].default_value = 0.0
        for l in LAMPS:
            l.data.energy = 0.0     # a lamp's direct light stays in the indirect map: the page draws only the sun live
        bpy.ops.object.bake(type='DIFFUSE', pass_filter={'DIRECT'}, uv_layer='lightmap', use_clear=True, margin=16)
        bg.inputs['Strength'].default_value = 1.0
        for l, e in zip(LAMPS, lamps_on):
            l.data.energy = e
    a = np.array(im.pixels[:], dtype=np.float32).reshape(res, res, 4)[..., :3]
    for m in o.data.materials:
        m.node_tree.nodes.remove(m.node_tree.nodes['__bake__'])
    bpy.data.images.remove(im)
    print('baked', o.name, kind, res, SPP[kind], 'spp', round(time.time() - t, 1), 's', flush=True)
    return a


LUM = np.array([0.2126, 0.7152, 0.0722])


def srgb8(a):
    s = np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(a, 1 / 2.4) - 0.055)
    return (s * 255 + 0.5).astype(np.uint8)[::-1]      # blender rows are bottom-up


def indirect(o, res, has_sun, path):
    """the light minus the sun's direct light, as the plaza's encode.py: baked / K, K = the 99.7th percentile * 1.15"""
    full = bake(o, 'full', res, path)
    ind = np.clip(full - bake(o, 'sundirect', res, path), 0, None) if has_sun else full
    lum = ind @ LUM
    lit = lum[(full @ LUM) > 1e-6]
    K = float(np.percentile(lit, 99.7)) * 1.15 if lit.size else 1.0
    Image.fromarray(srgb8(np.clip(ind / K, 0, 1)), 'RGB').filter(ImageFilter.GaussianBlur(0.7)).save(path, optimize=True)
    print(o.name, os.path.basename(path), 'K', round(K, 5), 'mean', ind.mean(axis=(0, 1)))
    return {'K': K, 'res': res}


# ---------------------------------------------------------------- the light sub-pack
assert SET in SETS, f'unknown light set {SET}'
d = f'{OUT}/light-{SET}'
os.makedirs(d, exist_ok=True)
meta = {'set': SET}
set_light(SETS[SET], meta)
for name in ('ground', 'arch'):
    meta[name] = indirect(bpy.data.objects[name], RES, 'sun' in SETS[SET], f'{d}/lm_{name}_indirect.png')
json.dump(meta, open(f'{d}/lm_meta.json', 'w'), indent=1)
print('light', SET, 'done')
