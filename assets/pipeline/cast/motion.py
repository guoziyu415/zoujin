"""Character-specific adjustments to the retargeted clips, before glTF export."""

import math

import bpy
from mathutils import Quaternion, Vector


def local_rotation(rig, name, degrees):
    rest = rig.data.bones[name].matrix_local.to_3x3()
    turn = Quaternion(Vector((1, 0, 0)), math.radians(degrees))
    return (rest.inverted() @ turn.to_matrix() @ rest).to_quaternion()


def style(rig):
    old_man = rig.get("cast_id") == "char.old-man"
    traveler = rig.get("cast_id") == "role.traveler"
    held_right = rig.get("cast_id") in {"char.guards", "char.travelers"}
    if not (old_man or traveler or held_right):
        return
    scene = bpy.context.scene
    animation = rig.animation_data
    tracks = list(animation.nla_tracks)
    source = {track.name: track.strips[0].action for track in tracks}
    for track in tracks:
        track.mute = True
    animation.action = source["idle"]
    animation.action_slot = source["idle"].slots[0]
    scene.frame_set(20)
    rest = {b.name: b.rotation_quaternion.copy() for b in rig.pose.bones}
    for name, action in source.items():
        animation.action = action
        animation.action_slot = action.slots[0]
        first, last = map(int, action.frame_range)
        frames = []
        for frame in range(first, last + 1):
            scene.frame_set(frame)
            quats = {b.name: b.rotation_quaternion.copy() for b in rig.pose.bones}
            position = rig.pose.bones["pelvis"].location.copy()
            if traveler:
                quats["upperarm_l"] = rest["upperarm_l"].copy()
                quats["lowerarm_l"] = local_rotation(rig, "lowerarm_l", -58) @ rest["lowerarm_l"]
                quats["hand_l"] = rest["hand_l"].copy()
                frames.append((frame, quats, position))
                continue
            if held_right:
                for bone in ("upperarm_r", "lowerarm_r", "hand_r"):
                    quats[bone] = rest[bone].copy()
                frames.append((frame, quats, position))
                continue
            for bone, angle in (("spine_01", 7), ("spine_02", 8), ("spine_03", 7), ("neck_01", -8)):
                if bone in quats:
                    quats[bone] = local_rotation(rig, bone, angle) @ quats[bone]
            # The cane arm keeps a quiet grip, instead of waving through the talk gesture.
            for bone in ("upperarm_r", "lowerarm_r", "hand_r"):
                quats[bone] = rest[bone].copy()
            quats["upperarm_r"] = local_rotation(rig, "upperarm_r", -22) @ quats["upperarm_r"]
            if name in {"walk", "run", "sprint"}:
                for bone in ("thigh_l", "thigh_r", "calf_l", "calf_r", "foot_l", "foot_r"):
                    quats[bone] = rest[bone].slerp(quats[bone], 0.55)
                position *= 0.55
            frames.append((frame, quats, position))
        replacement = bpy.data.actions.new(name + "_character")
        animation.action = replacement
        for frame, quats, position in frames:
            for bone, quaternion in quats.items():
                target = rig.pose.bones[bone]
                target.rotation_mode = "QUATERNION"
                target.rotation_quaternion = quaternion
                target.keyframe_insert("rotation_quaternion", frame=frame)
            rig.pose.bones["pelvis"].location = position
            rig.pose.bones["pelvis"].keyframe_insert("location", frame=frame)
        track = next(t for t in tracks if t.name == name)
        track.strips[0].action = replacement
        track.strips[0].action_slot = replacement.slots[0]
        replacement.use_fake_user = True
    animation.action = None
    for track in tracks:
        track.mute = False
    for bone in rig.pose.bones:
        bone.rotation_quaternion = (1, 0, 0, 0)
        bone.location = (0, 0, 0)
