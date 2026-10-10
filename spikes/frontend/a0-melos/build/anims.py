"""Procedural idle, walk and run clips for the stand-in rig (placeholders for CC0 mocap).

The real clips come from CC0 motion capture (Quaternius UAL / CMU) retargeted on the
Mac.  These exist so export, file size and playback can be tested now.
Rotations are written in armature rest axes (Z up, character faces -Y, left = +X)
and converted to each bone's local axes.  The clips are written for the MakeHuman default
rig of the stand-in; on MPFB's game_engine rig (the Melos build) build() maps the names and
measures how far the arms must come down from that rig's rest pose.
"""
import math

import bpy
from mathutils import Quaternion, Vector

FPS = 30
NAMES = {}        # stand-in bone -> bone of the rig being animated (filled by build())
ARM_DOWN = 38.0   # degrees from the rest A-pose to arms at the sides (stand-in; build() measures others)


def _game_engine_names():
    m = {'spine01': 'spine_03', 'spine03': 'spine_02', 'neck02': 'neck_01'}
    for big, s in (('L', 'l'), ('R', 'r')):
        m |= {f'upperarm01.{big}': f'upperarm_{s}', f'lowerarm01.{big}': f'lowerarm_{s}',
              f'upperleg01.{big}': f'thigh_{s}', f'lowerleg01.{big}': f'calf_{s}', f'foot.{big}': f'foot_{s}'}
        for i, f in enumerate(('thumb', 'index', 'middle', 'ring', 'pinky'), 1):
            m[f'finger{i}-1.{big}'] = f'{f}_01_{s}'
            m[f'finger{i}-2.{big}'] = f'{f}_02_{s}'
    return m


def _local(pb, q_arm):
    m = pb.bone.matrix_local.to_3x3()
    return (m.inverted() @ q_arm.to_matrix() @ m).to_quaternion()


def _rot(axis, deg):
    return Quaternion(Vector(axis), math.radians(deg))


def _key(rig, frame, pose):
    """pose: bone -> Quaternion in armature axes (relative to parent); '@loc' -> root offset."""
    for name, q in pose.items():
        if name == '@loc':
            pb = rig.pose.bones['root']
            pb.location = pb.bone.matrix_local.to_3x3().inverted() @ q
            pb.keyframe_insert('location', frame=frame)
            continue
        pb = rig.pose.bones.get(NAMES.get(name, name))
        if pb is None:
            continue
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = _local(pb, q)
        pb.keyframe_insert('rotation_quaternion', frame=frame)


def arms_down(pose, swing_l=0.0, swing_r=0.0, elbow=12.0):
    # rest pose is an A-pose; bring the arms to the sides, then swing forward/back about X
    pose['upperarm01.L'] = _rot((1, 0, 0), swing_l) @ _rot((0, 1, 0), ARM_DOWN)
    pose['upperarm01.R'] = _rot((1, 0, 0), swing_r) @ _rot((0, 1, 0), -ARM_DOWN)
    pose['lowerarm01.L'] = _rot((1, 0, 0), -elbow)
    pose['lowerarm01.R'] = _rot((1, 0, 0), -elbow)
    for s in 'LR':
        for i in range(1, 6):
            pose[f'finger{i}-1.{s}'] = _rot((1, 0, 0), -8)
            pose[f'finger{i}-2.{s}'] = _rot((1, 0, 0), -12)


def make_action(rig, name, seconds, fn):
    rig.animation_data_create()
    act = bpy.data.actions.new(name)
    rig.animation_data.action = act
    n = int(round(seconds * FPS))
    for f in range(0, n + 1, 2):
        t = f / FPS
        _key(rig, f + 1, fn(t, seconds))
    for pb in rig.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    track = rig.animation_data.nla_tracks.new()
    track.name = name
    track.strips.new(name, 1, act)
    rig.animation_data.action = None
    act.use_fake_user = True
    return act


def idle(t, T):
    w = 2 * math.pi * t / T
    pose = {}
    breathe = math.sin(2 * w)            # two breaths per 4 s loop
    shift = math.sin(w)                  # one slow weight shift
    pose['@loc'] = Vector((0.012 * shift, 0, -0.003 * abs(shift)))
    pose['spine03'] = _rot((1, 0, 0), -1.2 * breathe)
    pose['spine01'] = _rot((0, 1, 0), -1.0 * shift)
    pose['neck02'] = _rot((0, 0, 1), 2.5 * math.sin(w + 1.0))
    pose['head'] = _rot((1, 0, 0), 1.5 * math.sin(w * 2 + 0.5))
    arms_down(pose, 1.5 * breathe, 1.5 * breathe, 14)
    pose['upperleg01.L'] = _rot((0, 1, 0), -1.5 * shift)
    pose['upperleg01.R'] = _rot((0, 1, 0), -1.5 * shift)
    return pose


def walk(t, T):
    w = 2 * math.pi * t / T
    s = math.sin(w)
    pose = {'@loc': Vector((0.015 * s, 0, 0.018 * math.cos(2 * w) - 0.018))}
    pose['root'] = _rot((0, 0, 1), 4 * s)
    pose['spine03'] = _rot((0, 0, 1), -6 * s) @ _rot((1, 0, 0), -3)
    pose['head'] = _rot((0, 0, 1), 2 * s)
    for side, sg in (('L', 1), ('R', -1)):
        ph = s * sg                       # +1: this leg forward
        thigh = -24 * ph
        swing = max(0.0, math.cos(w) * sg)   # knee bends while the leg swings forward
        knee = 6 + 42 * swing
        pose[f'upperleg01.{side}'] = _rot((1, 0, 0), thigh)
        pose[f'lowerleg01.{side}'] = _rot((1, 0, 0), knee)
        pose[f'foot.{side}'] = _rot((1, 0, 0), -0.4 * knee + 0.3 * thigh)
    arms_down(pose, 16 * s, -16 * s, 18)
    return pose


def run(t, T):
    """Placeholder jog: forward lean, a flight phase (the root rises twice per cycle),
    bent elbows swinging against the legs. Real clip: CC0 mocap."""
    w = 2 * math.pi * t / T
    s = math.sin(w)
    # two bounces per cycle, lowest just after each foot lands
    bounce = 0.045 * abs(math.cos(w)) - 0.04
    pose = {'@loc': Vector((0.01 * s, 0, bounce))}
    pose['root'] = _rot((0, 0, 1), 5 * s)
    pose['spine01'] = _rot((1, 0, 0), -9)                      # lean into the run
    pose['spine03'] = _rot((0, 0, 1), -9 * s) @ _rot((1, 0, 0), -4)
    pose['neck02'] = _rot((1, 0, 0), 7)                        # keep the eyes level
    pose['head'] = _rot((0, 0, 1), 3 * s) @ _rot((1, 0, 0), 3)
    for side, sg in (('L', 1), ('R', -1)):
        ph = s * sg
        thigh = -36 * ph - 8
        swing = max(0.0, math.cos(w) * sg)
        knee = 18 + 85 * swing
        pose[f'upperleg01.{side}'] = _rot((1, 0, 0), thigh)
        pose[f'lowerleg01.{side}'] = _rot((1, 0, 0), knee)
        pose[f'foot.{side}'] = _rot((1, 0, 0), -0.35 * knee + 0.3 * thigh + 6)
    arms_down(pose, 34 * s, -34 * s, 85)
    return pose


def build(rig):
    global ARM_DOWN
    if 'upperarm_l' in rig.pose.bones:
        NAMES.update(_game_engine_names())
        b = rig.data.bones['upperarm_l']
        v = b.tail_local - b.head_local
        ARM_DOWN = 78.0 - math.degrees(math.atan2(-v.z, v.x))   # to 78 degrees below horizontal
    for tr in list(rig.animation_data.nla_tracks) if rig.animation_data else []:
        rig.animation_data.nla_tracks.remove(tr)
    a = make_action(rig, 'idle', 4.0, idle)
    b = make_action(rig, 'walk', 1.1, walk)
    c = make_action(rig, 'run', 0.72, run)
    return [a, b, c]
