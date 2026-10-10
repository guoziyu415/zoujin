# quick Cycles preview renders of plaza_raw.blend
import bpy, math, os, sys
from mathutils import Vector, Matrix
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
SAMPLES = int(argv[0]) if argv else 32
which = argv[1].split(',') if len(argv) > 1 else None
OUT = os.environ['PLAZA_OUT']  # work dir (build.sh sets it); nothing here is committed
bpy.ops.wm.open_mainfile(filepath=f'{OUT}/plaza_raw.blend')
scene = bpy.context.scene
ROT = Matrix.Rotation(math.radians(144.0), 4, 'Z')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sunpos import sun_local
SUN_LOCAL, _E, _A = sun_local(); SUN_ELEV = math.radians(_E)
print(f'sun at {_E:.2f} deg elevation, azimuth {_A:.1f}')

# world: the generated sky (sky.py)
world = bpy.data.worlds.new('World'); scene.world = world
world.use_nodes = True
N = world.node_tree.nodes; L = world.node_tree.links
bg = N['Background']
env = N.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(f'{OUT}/sky_sunset.hdr')
L.new(env.outputs['Color'], bg.inputs['Color']); bg.inputs['Strength'].default_value = 1.0

# sun lamp
sd = (ROT @ SUN_LOCAL).normalized()   # direction to the sun
ld = bpy.data.lights.new('Sun', 'SUN'); ld.energy = 6.0; ld.color = (1.0, 0.58, 0.32); ld.angle = math.radians(1.2)
lo = bpy.data.objects.new('Sun', ld); scene.collection.objects.link(lo)
lo.rotation_euler = (-sd).to_track_quat('-Z', 'Y').to_euler()

scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = 960, 540
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Punchy' if 'AgX - Punchy' in [i.identifier for i in scene.view_settings.bl_rna.properties['look'].enum_items] else 'None'
scene.render.image_settings.file_format = 'JPEG'

CAMS = {
    'entry': ((-24, -0.5, 1.7), (10, 1.5, 4.0), 24),
    'gate': ((8, 1.0, 1.7), (-40, -1.0, 3.5), 26),
    'castle': ((-10, -6, 1.7), (20, 2, 9.0), 22),
    'temple': ((2, 5, 1.7), (0, 22, 5.5), 22),
}
for name, (p, t, lens) in CAMS.items():
    if which and name not in which:
        continue
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.sensor_width = 36; cd.clip_end = 1000
    co = bpy.data.objects.new(name, cd); scene.collection.objects.link(co)
    P = ROT @ Vector(p); Tt = ROT @ Vector(t)
    co.location = P
    co.rotation_euler = (Tt - P).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = co
    scene.render.filepath = f'{OUT}/prev_{name}.jpg'
    bpy.ops.render.render(write_still=True)
    print('rendered', name)
