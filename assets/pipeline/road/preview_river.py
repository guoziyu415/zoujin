# Quick Cycles previews of one river pack (dev tool, not part of the build): the views the F-10 acceptance names.
#   cd <work dir of the state> && PLAZA_OUT=. SCENE_STEM=road-river-calm RIVER_STATE=calm \
#     <bpy python> assets/pipeline/road/preview_river.py -- [samples] [view,view]
# Uses the build's own sky (sky_sunset.hdr) and the sun the bake used (same env as build.sh's state_env).
import bpy, math, os, sys
from mathutils import Vector
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
SAMPLES = int(argv[0]) if argv else 24
which = argv[1].split(',') if len(argv) > 1 else None
OUT = os.environ['PLAZA_OUT']
STEM = os.environ['SCENE_STEM']
FLOOD = os.environ['RIVER_STATE'] == 'flood'
bpy.ops.wm.open_mainfile(filepath=f'{OUT}/{STEM}_raw.blend')
scene = bpy.context.scene
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'plaza'))
from sunpos import sun_local
SUN_LOCAL, _E, _A = sun_local()
print(f'sun at {_E:.2f} deg elevation, azimuth {_A:.1f}')

world = bpy.data.worlds.new('World'); scene.world = world
world.use_nodes = True
N = world.node_tree.nodes; L = world.node_tree.links
env = N.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(f'{OUT}/sky_sunset.hdr')
L.new(env.outputs['Color'], N['Background'].inputs['Color'])
E = float(os.environ.get('BAKE_SUN_E', '6'))
if E > 0:
    ld = bpy.data.lights.new('Sun', 'SUN'); ld.energy = E; ld.angle = math.radians(1.2)
    ld.color = tuple(float(c) for c in os.environ.get('BAKE_SUN_RGB', '1,0.58,0.32').split(','))
    lo = bpy.data.objects.new('Sun', ld); scene.collection.objects.link(lo)
    lo.rotation_euler = (-SUN_LOCAL.normalized()).to_track_quat('-Z', 'Y').to_euler()

# the water as the page will roughly draw it: glossy, brown and opaque in flood, dark and clear-ish calm
w = bpy.data.materials['water']
b = w.node_tree.nodes['Principled BSDF']
b.inputs['Base Color'].default_value = (0.2, 0.14, 0.07, 1) if FLOOD else (0.02, 0.035, 0.035, 1)
b.inputs['Roughness'].default_value = 0.12 if FLOOD else 0.03
if not FLOOD:   # the mist on the calm water: a thin volume box over the channel
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    me = bpy.data.meshes.new('mist'); bm.to_mesh(me)
    o = bpy.data.objects.new('mist', me); scene.collection.objects.link(o)
    o.scale = (10.0, 90.0, 2.8); o.location = (2.6, 0, -2.0 + 1.4)
    m = bpy.data.materials.new('mist'); m.use_nodes = True
    nt = m.node_tree; nt.nodes.remove(nt.nodes['Principled BSDF'])
    v = nt.nodes.new('ShaderNodeVolumePrincipled'); v.inputs['Density'].default_value = 0.06
    nt.links.new(v.outputs['Volume'], nt.nodes['Material Output'].inputs['Volume'])
    me.materials.append(m)

scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'
scene.cycles.samples = SAMPLES; scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = 960, 540
scene.view_settings.view_transform = 'AgX'
scene.view_settings.exposure = float(os.environ.get('PREVIEW_EV', '1.2' if not FLOOD else '-0.6'))
scene.render.image_settings.file_format = 'JPEG'

EYE = 1.6
CAMS = {   # name: (eye, target, lens)
    'calm-east': ((17, 1, EYE), (-6, 0, 0.5), 24),          # from road-east: Melos at the wash, the bridge, the mist
    'calm-bridge': ((9, 0.2, EYE), (-20, -2, 1.0), 28),
    'calm-north': ((2, -0.3, EYE), (3, 40, 2.0), 24),        # up the valley to the shallows
    'flood-west': ((-16, -1, EYE), (10, 0, 0.5), 24),        # from road-west: the broken piles, the water, the willow
    'flood-south': ((-6.5, 2, EYE), (-2, -40, -0.5), 26),    # 11:45 into the light downstream
    'flood-bank': ((-6, 0.8, EYE), (8, -2, -0.2), 30),       # melos-bridgehead
}
for name, (p, t, lens) in CAMS.items():
    if name.startswith('calm') == FLOOD or (which and name not in which):
        continue
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.sensor_width = 36; cd.clip_end = 1500
    co = bpy.data.objects.new(name, cd); scene.collection.objects.link(co)
    co.location = Vector(p); co.rotation_euler = (Vector(t) - Vector(p)).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = co
    scene.render.filepath = f'{OUT}/prev_{name}.jpg'
    bpy.ops.render.render(write_still=True)
    print('rendered', name)
