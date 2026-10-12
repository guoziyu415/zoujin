"""Render one exported character for local visual QA (not a replacement for phone QA).

  BPY_PYTHON -I assets/pipeline/cast/preview.py <raw GLB> <raw anims GLB> <output directory>

Use the uncompressed exports retained by CAST_QA_DIR. Renders actual exported geometry and the idle / walk clips,
with consistent neutral light, a ground plane, front/back/side views and a face crop. Outputs stay outside Git.
"""

import math
import os
import sys

import bpy  # first: mathutils is supplied by bpy
from mathutils import Vector  # noqa: E402

model, clips, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=os.path.abspath(model))
rig = next(o for o in scene.objects if o.type == "ARMATURE")
parts = [
    o
    for o in scene.objects
    if o.type == "MESH" and len(o.data.vertices) and any(mod.type == "ARMATURE" for mod in o.modifiers)
]
for ob in parts:
    if ob.data.shape_keys:
        for key in ob.data.shape_keys.key_blocks:
            key.value = 0
before = set(scene.objects)
bpy.ops.import_scene.gltf(filepath=os.path.abspath(clips))
clip_rig = next(o for o in scene.objects if o not in before and o.type == "ARMATURE")
tracks = list(clip_rig.animation_data.nla_tracks)
actions = {t.name.split("_")[0]: t.strips[0].action for t in tracks}
print("QA_ACTIONS", {k: a.name for k, a in actions.items()})
for ob in list(scene.objects):
    if ob not in before:
        bpy.data.objects.remove(ob, do_unlink=True)
rig.animation_data_create()
for track in list(rig.animation_data.nla_tracks):
    rig.animation_data.nla_tracks.remove(track)


def pose(name, frame):
    action = actions.get(name)
    if action is None:
        raise ValueError(f"Missing exported {name} animation")
    rig.animation_data.action = action
    if action.slots:
        rig.animation_data.action_slot = action.slots[0]
    scene.frame_set(frame)
    bpy.context.view_layer.update()


pose("idle", 20)
deps = bpy.context.evaluated_depsgraph_get()
points = [ob.matrix_world @ v.co for ob in parts for v in ob.evaluated_get(deps).data.vertices]
low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
height = high.z - low.z
print("QA_BOUNDS", list(low), list(high), "height", height)

world = bpy.data.worlds.new("QA neutral studio")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.24, 0.27, 0.30, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
scene.world = world


def aim(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()


for name, at, power, size, colour in (
    ("key", (-3, -4, 5), 650, 4, (1.0, 0.86, 0.72)),
    ("fill", (3, -1, 3), 260, 4, (0.77, 0.86, 1.0)),
    ("rim", (1, 3, 4), 500, 3, (1.0, 0.92, 0.82)),
):
    data = bpy.data.lights.new(name, "AREA")
    data.energy, data.shape, data.size, data.color = power, "DISK", size, colour
    light = bpy.data.objects.new(name, data)
    scene.collection.objects.link(light)
    light.location = at
    aim(light, (0, 0, 1))

bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, low.z - 0.005))
floor = bpy.context.object
material = bpy.data.materials.new("neutral floor")
material.diffuse_color = (0.23, 0.25, 0.27, 1)
floor.data.materials.append(material)

data = bpy.data.cameras.new("QA camera")
data.type, data.ortho_scale, data.lens = "ORTHO", height * 1.14, 70
camera = bpy.data.objects.new("QA camera", data)
scene.collection.objects.link(camera)
scene.camera = camera
scene.render.engine = "CYCLES"
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.threads_mode = "FIXED"
scene.render.threads = 4
scene.render.resolution_x, scene.render.resolution_y = 560, 700
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "AgX"
scene.render.film_transparent = False

for name, angle, animation, frame in (
    ("front", 0, "idle", 20),
    ("back", math.pi, "idle", 20),
    ("side", math.pi / 2, "idle", 20),
    ("walk", math.pi / 4, "walk", 12),
    ("face", 0.25, "talk", 25),
):
    pose(animation, frame)
    target = Vector((0, 0, low.z + height * (0.87 if name == "face" else 0.5)))
    camera.location = target + Vector((math.sin(angle) * 5, -math.cos(angle) * 5, 0.12))
    camera.data.ortho_scale = height * (0.34 if name == "face" else 1.14)
    aim(camera, target)
    scene.render.filepath = os.path.join(out, name + ".png")
    bpy.ops.render.render(write_still=True)
