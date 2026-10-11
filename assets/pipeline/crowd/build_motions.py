"""The crowd's standing motions (F-4) from Quaternius's Universal Animation Library (UAL1_Standard.glb, CC0): its idle
and its idle while talking, carried over onto the nine roles the runtime animates (apps/web/src/three/crowd/rig.ts).

  python build_motions.py -- <UAL1_Standard.glb> <out_dir>

Writes <out_dir>/motions.json next to crowd.json; the runtime uses it in place of its own sway when the pack has it.
The animation file itself never goes in the repo (build.sh takes it from UAL_GLB and checks its sha256).

How: UAL's skeleton has the same bone names as MPFB's game_engine rig, but its rest is a T pose and the crowd's is
arms down. So each bone's motion is taken as its world rotation against the same bone in the idle's first frame (a
standing pose close to the crowd's rest), and each role gets that rotation relative to its parent role's: a body at
rest is the idle's first frame. The hips' offset is the pelvis's, against the same frame. Legs aren't carried (the
crowd's feet stay planted); the hips role is spine_01, so the pelvis's turn goes to the upper body.

Coordinates out: three.js (Y up, facing +Z, left +X); each role's rotation as x, y, z radians in three's XYZ order.
"""

import hashlib
import json
import math
import os
import sys

import bpy  # first: mathutils only imports once bpy has  # isort: skip

from mathutils import Quaternion  # noqa: E402

FPS = 30  # the runtime's (rig.ts FPS)
# role -> (UAL bone, parent role); the arms' parent is the chest (the clavicle doesn't move in the crowd)
ROLES = {
    "hips": ("spine_01", None),
    "spine": ("spine_02", "hips"),
    "chest": ("spine_03", "spine"),
    "neck": ("neck_01", "chest"),
    "head": ("Head", "neck"),
    "armL": ("upperarm_l", "chest"),
    "foreL": ("lowerarm_l", "armL"),
    "armR": ("upperarm_r", "chest"),
    "foreR": ("lowerarm_r", "armR"),
}
REFERENCE = "Idle_Loop"  # its first frame is the crowd's rest
CLIPS = {"sway": "Idle_Loop", "talk": "Idle_Talking_Loop"}  # runtime name -> UAL action


def to_three(q):
    """A Blender (Z up, facing -Y) rotation as three's (Y up, facing +Z): (x, y, z) -> (x, z, -y)."""
    return Quaternion((q.w, q.x, q.z, -q.y))


def xyz(q):
    # three's Euler "XYZ" is the matrix Rx·Ry·Rz, which mathutils calls "ZYX"
    e = q.to_euler("ZYX")
    return [e.x, e.y, e.z]


def pose_at(arm, action, seconds):
    ad = arm.animation_data
    if ad.action != action:
        ad.action = action
        if getattr(ad, "action_suitable_slots", None):
            ad.action_slot = ad.action_suitable_slots[0]
    fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
    f = action.frame_range[0] + seconds * fps
    bpy.context.scene.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
    bpy.context.view_layer.update()
    rot = {r: (arm.matrix_world @ arm.pose.bones[b].matrix).to_quaternion() for r, (b, _) in ROLES.items()}
    pelvis = arm.matrix_world @ arm.pose.bones["pelvis"].head
    return rot, pelvis.copy()


def main():
    glb, out_dir = sys.argv[sys.argv.index("--") + 1 :][:2]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=glb)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    arm.animation_data_create()
    ref_rot, ref_pelvis = pose_at(arm, bpy.data.actions[REFERENCE], 0)
    scene_fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
    clips = {}
    for name, source in CLIPS.items():
        action = bpy.data.actions[source]
        seconds = (action.frame_range[1] - action.frame_range[0]) / scene_fps
        frames = round(seconds * FPS)
        rows = []
        for f in range(frames):
            rot, pelvis = pose_at(arm, action, min(f / FPS, seconds))
            world = {r: rot[r] @ ref_rot[r].inverted() for r in ROLES}  # each bone against the reference frame
            row = []
            d = pelvis - ref_pelvis
            row += [d.x, d.z, -d.y]
            for r, (_, parent) in ROLES.items():
                local = world[parent].inverted() @ world[r] if parent else world[r]
                row += xyz(to_three(local))
            rows.append([round(v, 4) for v in row])
        clips[name] = {"source": source, "seconds": round(frames / FPS, 4), "loop": True, "frames": rows}
    with open(__file__, "rb") as f:
        script = hashlib.sha256(f.read()).hexdigest()
    with open(glb, "rb") as f:
        source = hashlib.sha256(f.read()).hexdigest()
    out = {
        "format": "zoujin-crowd-motions-1",
        "note": "Quaternius Universal Animation Library (CC0), carried onto the crowd's roles by build_motions.py",
        "inputs": {"UAL1_Standard.glb": source, "assets/pipeline/crowd/build_motions.py": script},
        "fps": FPS,
        "row": ["hips offset x, y, z"] + [f"{r} x, y, z" for r in ROLES],
        "roles": list(ROLES),
        "clips": clips,
    }
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "motions.json"), "w") as f:
        json.dump(out, f, separators=(",", ":"))
    for name, c in clips.items():
        print(f"{name}: {c['source']}, {c['seconds']} s, {len(c['frames'])} frames")


if __name__ == "__main__":
    main()
