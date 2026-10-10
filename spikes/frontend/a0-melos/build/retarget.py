"""Retarget Quaternius' Universal Animation Library (CC0, UAL1_Standard.glb, in place) onto MPFB's game_engine rig.

Both skeletons use the Unreal mannequin names and face -Y; UAL rests in a T-pose, the MPFB rig in an A-pose with the
forearms forward. Per bone, in armature space:
  1. align: swing the target bone so it points where the source bone points at rest (target T-pose);
  2. each frame, give it the same rotation the source bone has from its rest: P = (S_pose @ S_rest^-1) @ align @ T_rest.
The pelvis also follows the source pelvis' offset from rest, scaled by hip height. Bones the source lacks (bundle)
follow their parent. Local pose = what Blender would need to produce P, computed directly (no depsgraph per bone).
Also measures each clip's ground speed (foot sliding back while planted) so the game can set the playback rate.
"""
import bpy
from mathutils import Matrix, Vector

# clip in the game -> UAL action
CLIPS = {
    'idle': 'Idle_Loop',
    'talk': 'Idle_Talking_Loop',
    'walk': 'Walk_Loop',
    'run': 'Jog_Fwd_Loop',
    'sprint': 'Sprint_Loop',
}
RENAME = {'Head': 'head'}


def _import(path):
    before = set(bpy.data.objects)
    acts_before = set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    src = next(o for o in new if o.type == 'ARMATURE')
    return src, new, [a for a in bpy.data.actions if a not in acts_before]


def _rest(arm):
    return {b.name: b.matrix_local.copy() for b in arm.data.bones}


def _dir(b):
    return (b.tail_local - b.head_local).normalized()


def _ground_speed(src, act, frames, fps):
    """m/s the planted foot slides back (= walking speed for a clip played in place); 0 for standing clips."""
    speeds = []
    for side in 'lr':
        pb = src.pose.bones[f'ball_{side}']
        pts = []
        for f in frames:
            bpy.context.scene.frame_set(f)
            pts.append((src.matrix_world @ pb.head).copy())
        low = min(p.z for p in pts)
        for a, b in zip(pts, pts[1:]):
            if a.z < low + 0.02 and b.z < low + 0.02:   # planted
                speeds.append(abs(b.y - a.y) * fps)
    if not speeds:
        return 0.0
    speeds.sort()
    return speeds[len(speeds) // 2]


def build(rig, glb_path, fps=24):
    scene = bpy.context.scene
    scene.render.fps = fps
    src, imported, acts = _import(glb_path)
    src_rest = _rest(src)
    tgt_rest = _rest(rig)
    sb = src.data.bones
    tb = rig.data.bones
    pairs = {}
    for b in sb:
        t = RENAME.get(b.name, b.name)
        if t in tb and t != 'root':
            pairs[t] = b.name
    align = {}
    for t, s in pairs.items():
        q = _dir(tb[t]).rotation_difference(_dir(sb[s]))
        align[t] = q.to_matrix().to_4x4() @ Matrix.Translation(-tgt_rest[t].translation) @ tgt_rest[t]
    hip = tgt_rest['pelvis'].translation.z / src_rest['pelvis'].translation.z

    for tr in list(rig.animation_data.nla_tracks) if rig.animation_data else []:
        rig.animation_data.nla_tracks.remove(tr)
    rig.animation_data_create()
    src.animation_data_create()
    order = [b for b in tb]                       # parents come before children in Blender's bone list
    report = {}
    out = []
    mine = {a.name.rsplit('.', 1)[0] if a.name[-4:-3] == '.' else a.name: a for a in acts}   # Idle_Loop.001 etc.
    for clip, ual in CLIPS.items():
        sa = mine[ual]
        src.animation_data.action = sa
        if src.animation_data.action_slot is None and sa.slots:   # Blender 4.4+ slotted actions
            src.animation_data.action_slot = sa.slots[0]
        f0, f1 = (int(round(v)) for v in sa.frame_range)
        act = bpy.data.actions.new(clip)
        rig.animation_data.action = act
        for f in range(f0, f1 + 1):
            scene.frame_set(f)
            pose = {}                             # target bone -> armature-space matrix this frame
            for b in order:
                parent = b.parent
                inherited = (pose[parent.name] @ tgt_rest[parent.name].inverted() @ tgt_rest[b.name]
                             if parent else tgt_rest[b.name].copy())
                s = pairs.get(b.name)
                if s is None:
                    pose[b.name] = inherited
                    continue
                sp = src.pose.bones[s].matrix
                delta = sp.to_3x3() @ src_rest[s].to_3x3().inverted()
                rot = (delta @ align[b.name].to_3x3()).normalized()
                head = inherited.translation
                if b.name == 'pelvis':
                    head = tgt_rest['pelvis'].translation + (sp.translation - src_rest[s].translation) * hip
                pose[b.name] = Matrix.Translation(head) @ rot.to_4x4()
            for b in order:
                pb = rig.pose.bones[b.name]
                parent = b.parent
                ppose = pose[parent.name] if parent else Matrix.Identity(4)
                prest = tgt_rest[parent.name] if parent else Matrix.Identity(4)
                basis = (prest.inverted() @ tgt_rest[b.name]).inverted() @ ppose.inverted() @ pose[b.name]
                loc, q, _ = basis.decompose()
                pb.rotation_mode = 'QUATERNION'
                pb.rotation_quaternion = q
                pb.keyframe_insert('rotation_quaternion', frame=f - f0 + 1)
                if b.name == 'pelvis':
                    pb.location = loc
                    pb.keyframe_insert('location', frame=f - f0 + 1)
        for pb in rig.pose.bones:
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.location = (0, 0, 0)
        track = rig.animation_data.nla_tracks.new()
        track.name = clip
        track.strips.new(clip, 1, act)
        rig.animation_data.action = None
        act.use_fake_user = True
        speed = _ground_speed(src, sa, range(f0, f1 + 1), fps) * hip
        report[clip] = {'from': ual, 'frames': f1 - f0 + 1, 'seconds': round((f1 - f0) / fps, 3),
                        'ground_speed': round(speed, 3)}
        out.append(act)

    src.animation_data.action = None
    for o in imported:
        bpy.data.objects.remove(o, do_unlink=True)
    for a in acts:
        bpy.data.actions.remove(a)
    scene.frame_set(1)
    return out, report
