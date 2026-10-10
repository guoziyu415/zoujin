# S7: join groups, make lightmap UVs, bake 3 lighting variants, export glTF.
import bpy, math, sys, os, time
import numpy as np
from mathutils import Vector, Matrix
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
Q = argv[0] if argv else 'final'          # 'draft' or 'final'
OUT = '/tmp/spk/s7build'
bpy.ops.wm.open_mainfile(filepath=f'{OUT}/plaza_raw.blend')
scene = bpy.context.scene
vl = bpy.context.view_layer
ROT = Matrix.Rotation(math.radians(144.0), 4, 'Z')
import sys as _s; _s.path.insert(0, '/tmp/spk/s7build')
from sunpos import sun_local
SUN_LOCAL, _E, _A = sun_local(); SUN_ELEV = math.radians(_E)
print(f'sun at {_E:.2f} deg elevation, azimuth {_A:.1f}')
SUN_E, SUN_C = 6.0, (1.0, 0.58, 0.32)
RES = {'ground': 2048, 'arch': 2048} if Q == 'final' else {'ground': 512, 'arch': 512}
SPP = {'full': 96, 'sundirect': 24, 'ao': 32} if Q == 'final' else {'full': 8, 'sundirect': 4, 'ao': 4}

# ---------- world + sun (same as preview.py; three.js uses the same numbers)
world = bpy.data.worlds.new('World'); scene.world = world
world.use_nodes = True
WN = world.node_tree.nodes; WL = world.node_tree.links
bg = WN['Background']
env = WN.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(f'{OUT}/sky_sunset.hdr')
WL.new(env.outputs['Color'], bg.inputs['Color']); bg.inputs['Strength'].default_value = 1.0
sd = (ROT @ SUN_LOCAL).normalized()
ld = bpy.data.lights.new('Sun', 'SUN'); ld.energy = SUN_E; ld.color = SUN_C; ld.angle = math.radians(1.2)
sun = bpy.data.objects.new('Sun', ld); scene.collection.objects.link(sun)
sun.rotation_euler = (-sd).to_track_quat('-Z', 'Y').to_euler()
print('SUN_DIR_TO_SUN (blender)', tuple(round(c, 5) for c in sd))

scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.render.bake.margin = 16
scene.render.bake.margin_type = 'EXTEND'

def select_only(objs, active=None):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    vl.objects.active = active or objs[0]

def join_group(gname, newname):
    objs = [o for o in bpy.data.collections[gname].objects if o.type == 'MESH']
    select_only(objs)
    bpy.ops.object.join()
    o = vl.objects.active
    o.name = newname; o.data.name = newname
    return o

# ---------- shadow proxy: copies of the big casters, before joining
casters = [o for o in bpy.data.collections['arch'].objects if o.get('caster') == 1]
proxy_objs = []
pc = bpy.data.collections.new('proxy'); scene.collection.children.link(pc)
for o in casters:
    c = o.copy(); c.data = o.data.copy(); pc.objects.link(c)
    c.data.materials.clear()
    proxy_objs.append(c)
select_only(proxy_objs); bpy.ops.object.join()
proxy = vl.objects.active; proxy.name = 'proxy'; proxy.data.name = 'proxy'
for uv in list(proxy.data.uv_layers):
    proxy.data.uv_layers.remove(uv)
pm = bpy.data.materials.new('proxy_mat'); proxy.data.materials.append(pm)
proxy.hide_render = True

arch = join_group('arch', 'arch')
ground = bpy.data.objects['ground']
far = join_group('far', 'far')

# ---------- lightmap UVs
def make_lm_uv(o, planar=False):
    me = o.data
    lm = me.uv_layers.get('lightmap') or me.uv_layers.new(name='lightmap')
    me.uv_layers['UVMap'].active_render = True
    me.uv_layers.active = lm
    if planar:
        RI = ROT.inverted()
        loc = [RI @ v.co for v in me.vertices]
        xs = [c.x for c in loc]; ys = [c.y for c in loc]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        for poly in me.polygons:
            for li in poly.loop_indices:
                co = loc[me.loops[li].vertex_index]
                lm.data[li].uv = ((co.x - x0) / (x1 - x0), (co.y - y0) / (y1 - y0))
        return
    select_only([o])
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=0.004, rotate=True, shape_method='CONCAVE')
    bpy.ops.object.mode_set(mode='OBJECT')
    me = o.data
    print('UV layers', o.name, [u.name for u in me.uv_layers])
    me.uv_layers.active = me.uv_layers['lightmap']
    me.uv_layers['UVMap'].active_render = True

t0 = time.time()
make_lm_uv(ground, planar=True)
make_lm_uv(arch)
print('uv done', round(time.time() - t0, 1), 's')

# ---------- bake helpers
def bake_target(o, name, res):
    im = bpy.data.images.new(name, res, res, float_buffer=True)
    for m in o.data.materials:
        nt = m.node_tree
        n = nt.nodes.get('__bake__') or nt.nodes.new('ShaderNodeTexImage')
        n.name = '__bake__'; n.image = im
        for x in nt.nodes:
            x.select = False
        n.select = True; nt.nodes.active = n
    return im

def save_np(im, path):
    a = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)
    np.save(path, a[..., :3])
    return a

def do_bake(o, kind):
    res = RES[o.name]
    im = bake_target(o, f'{o.name}_{kind}', res)
    select_only([o])
    scene.cycles.samples = SPP[kind]
    t = time.time()
    if kind == 'full':
        bg.inputs['Strength'].default_value = 1.0; ld.energy = SUN_E
        bpy.ops.object.bake(type='DIFFUSE', pass_filter={'DIRECT', 'INDIRECT'}, uv_layer='lightmap', use_clear=True, margin=16)
    elif kind == 'sundirect':
        bg.inputs['Strength'].default_value = 0.0; ld.energy = SUN_E
        bpy.ops.object.bake(type='DIFFUSE', pass_filter={'DIRECT'}, uv_layer='lightmap', use_clear=True, margin=16)
    elif kind == 'ao':
        bg.inputs['Strength'].default_value = 1.0; ld.energy = SUN_E
        world.light_settings.distance = 4.0
        bpy.ops.object.bake(type='AO', uv_layer='lightmap', use_clear=True, margin=16)
    save_np(im, f'{OUT}/bake_{o.name}_{kind}.npy')
    print('baked', o.name, kind, res, SPP[kind], 'spp', round(time.time() - t, 1), 's', flush=True)

for o in (ground, arch):
    for kind in ('ao', 'sundirect', 'full'):
        do_bake(o, kind)

bg.inputs['Strength'].default_value = 1.0; ld.energy = SUN_E
# remove bake nodes before export
for m in bpy.data.materials:
    if m.node_tree and '__bake__' in m.node_tree.nodes:
        m.node_tree.nodes.remove(m.node_tree.nodes['__bake__'])

bpy.ops.wm.save_as_mainfile(filepath=f'{OUT}/plaza_baked.blend')
select_only([ground, arch, far, proxy])
proxy.hide_render = False
bpy.ops.export_scene.gltf(filepath=f'{OUT}/plaza_raw.glb', export_format='GLB', use_selection=True,
                          export_texcoords=True, export_normals=True, export_materials='EXPORT',
                          export_image_format='AUTO', export_apply=True, export_yup=True, export_extras=False)
print('exported')
