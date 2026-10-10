"""Cycles preview renders of a character blend: full body, face, face with shape keys.

/tmp/bpyenv/bin/python preview.py out/standin.blend out/prev [samples] [shape=value,...]
"""
import math
import sys

import bpy
from mathutils import Vector

blend, prefix = sys.argv[1], sys.argv[2]
samples = int(sys.argv[3]) if len(sys.argv) > 3 else 24
keys = {}
if len(sys.argv) > 4:
    for kv in sys.argv[4].split(','):
        k, val = kv.split('=')
        keys[k] = float(val)

bpy.ops.wm.open_mainfile(filepath=blend)
scene = bpy.context.scene
world = bpy.data.worlds.new('W')
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes['Background']
bg.inputs['Color'].default_value = (0.55, 0.62, 0.75, 1)
bg.inputs['Strength'].default_value = 0.6

# low evening sun from the west-ish, warm (art-direction 3.2: 17:30)
ld = bpy.data.lights.new('Sun', 'SUN')
ld.energy = 4.0
ld.color = (1.0, 0.72, 0.48)
ld.angle = math.radians(1.5)
lo = bpy.data.objects.new('Sun', ld)
scene.collection.objects.link(lo)
lo.rotation_euler = (math.radians(70), 0, math.radians(-50))
fill = bpy.data.lights.new('Fill', 'AREA')
fill.energy = 60
fill.size = 2
fo = bpy.data.objects.new('Fill', fill)
scene.collection.objects.link(fo)
fo.location = (1.5, -2.0, 1.8)
fo.rotation_euler = (Vector((0, 0, 1.6)) - fo.location).to_track_quat('-Z', 'Y').to_euler()

scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = samples
scene.cycles.use_denoising = True
scene.view_settings.view_transform = 'AgX'
scene.render.image_settings.file_format = 'JPEG'

for ob in scene.objects:
    sk = ob.data.shape_keys if ob.type == 'MESH' and ob.data.shape_keys else None
    if sk:
        for kb in sk.key_blocks[1:]:
            kb.value = keys.get(kb.name, 0.0)

body = bpy.data.objects['Body']
zs = [(body.matrix_world @ v.co).z for v in body.data.vertices]
top = max(zs)
CAMS = {
    'full': ((0.0, -4.2, 1.0), (0, 0, 0.92), 50, (540, 960)),
    'face': ((0.06, -0.95, top - 0.11), (0, 0, top - 0.13), 70, (720, 720)),
    'face34': ((0.55, -0.75, top - 0.09), (0, 0, top - 0.13), 70, (720, 720)),
}
for name, (p, t, lens, res) in CAMS.items():
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    co = bpy.data.objects.new(name, cd)
    scene.collection.objects.link(co)
    co.location = Vector(p)
    co.rotation_euler = (Vector(t) - Vector(p)).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = co
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.filepath = f'{prefix}_{name}.jpg'
    bpy.ops.render.render(write_still=True)
    print('rendered', name)
