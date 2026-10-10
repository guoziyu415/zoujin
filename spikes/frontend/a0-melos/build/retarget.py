"""Retarget Quaternius' Universal Animation Library (CC0, UAL1_Standard.glb, in place) onto MPFB's game_engine rig.

Both skeletons use the Unreal mannequin names and face -Y; UAL rests in a T-pose, the MPFB rig in an A-pose with the
forearms forward. Per bone, in armature space:
  1. align: swing the target bone so it points where the source bone points at rest (target T-pose);
  2. each frame, give it the same rotation the source bone has from its rest: P = (S_pose @ S_rest^-1) @ align @ T_rest.
The pelvis also follows the source pelvis' offset from rest, scaled by hip height. Bones the source lacks (bundle)
follow their parent. Local pose = what Blender would need to produce P, computed directly (no depsgraph per bone).

UAL's jog and sprint are game-style bounds (UX round 3: 2.8 m steps, 24 cm pelvis bob, heels above the hips), so
STYLE tones them down towards a real run before keying: each listed bone's swing around its mean pose is scaled, the
knees bend less (scaled from their straightest frame), the arms come in towards the idle pose, the pelvis bobs less,
and the pelvis is then lifted or lowered so the planted foot stays on the ground. The game matches the playback rate
to the walking speed (moveSpeed / ground_speed), so shorter strides also mean a quicker cadence.

Sampled at the source's own 30 fps, so every key is a source key and the loops close exactly. The report has each
clip's ground speed (the planted foot sliding back) and the gait numbers UX measures (cadence at a given speed, step
length, flight, pelvis bob, how high the swinging foot goes).
"""
import math

import bpy
from mathutils import Matrix, Quaternion, Vector

# clip in the game -> UAL action
CLIPS = {
    'idle': 'Idle_Loop',
    'talk': 'Idle_Talking_Loop',
    'walk': 'Walk_Loop',
    'run': 'Jog_Fwd_Loop',
    'sprint': 'Sprint_Loop',
}
RENAME = {'Head': 'head'}
FPS = 30

# contact: share of the loop with a foot planted (time warp); swing: bone -> scale of its swing around the clip's mean;
# arms_in: how far the upper arms' mean pose moves towards idle's; knee: bone -> (stance, swing) scale of its bend
# beyond the straightest frame; bend: the same in every frame; rise: how far the pelvis may rise in stance above its
# lowest stance height (the planted leg bends to reach). speed: what the game plays it at (test page GAIT_SPEED;
# the sprint is Melos coming in at the end, spent, at about 6.5 m/s), for the time in the air and the report.
# Tuned against UX round 3 (real run at 4.9 m/s: 165-180 steps/min, about 1.7 m a step, pelvis 7-10 cm, swinging
# foot about knee high): run 164 steps/min, 1.8 m, 8 cm, ankle at most 0.39 m (knee 0.51 m). Sprint at 6.5 m/s:
# 195 steps/min, 2.0 m, 7 cm, ankle at most 0.27 m (UX: heel at most 0.8 m, pelvis at most 8 cm).
STYLE = {
    'run': {
        'contact': 0.45,
        'swing': {'upperarm_l': 0.75, 'upperarm_r': 0.75, 'spine_01': 0.7, 'spine_02': 0.7, 'spine_03': 0.7,
                  'pelvis': 0.7},
        'arms_in': 0.5,
        'knee': {'calf_l': (1.0, 0.9), 'calf_r': (1.0, 0.9)},
        'bend': {'lowerarm_l': 0.85, 'lowerarm_r': 0.85},
        'rise': 0.025,
        'speed': 4.9,
    },
    'sprint': {
        'contact': 0.38,
        'swing': {'upperarm_l': 0.8, 'upperarm_r': 0.8, 'pelvis': 0.8},
        'arms_in': 0.3,
        'knee': {'calf_l': (1.0, 0.7), 'calf_r': (1.0, 0.7)},
        'rise': 0.03,
        'speed': 6.5,
    },
    'walk': {'speed': 1.15},
}
FEET = ('ball_l', 'ball_r')
HEELS = ('foot_l', 'foot_r')


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


def _mean(qs):
    """average rotation (component mean on one hemisphere; fine for poses within a loop)"""
    ref = tuple(qs[0])
    acc = [0.0, 0.0, 0.0, 0.0]
    for q in qs:
        v = tuple(q)
        sign = 1.0 if sum(a * b for a, b in zip(v, ref)) >= 0 else -1.0
        acc = [a + sign * b for a, b in zip(acc, v)]
    return Quaternion(acc).normalized()


def _part(d, k):
    """k of rotation d (the short way round)"""
    if d.w < 0:
        d = -d
    return Quaternion(d.axis, d.angle * k) if d.angle > 1e-9 else Quaternion()


def _scale_from(ref, q, k):
    """q's rotation away from ref, scaled by k"""
    return ref @ _part(ref.inverted() @ q, k)


class Fk:
    """Armature-space pose from local rotations plus the pelvis' armature-space position (root stays at rest)."""

    def __init__(self, rig, rest):
        self.order = [b for b in rig.data.bones]
        self.rest = rest
        self.rel = {b.name: (rest[b.parent.name].inverted() @ rest[b.name]) if b.parent else rest[b.name]
                    for b in self.order}

    def pose(self, quats, pelvis):
        out = {}
        for b in self.order:
            q = quats.get(b.name, Quaternion())
            m = (out[b.parent.name] @ self.rel[b.name]) if b.parent else self.rel[b.name].copy()
            m = m @ q.to_matrix().to_4x4()
            if b.name == 'pelvis':
                m.translation = pelvis
            out[b.name] = m
        return out


def _stance(fk, frames, floor):
    """per foot, the frames it is planted: its ball within 3 cm of its lowest (UAL's sprint never puts the ball flat
    on the floor); none for a foot that never comes within 8 cm of the floor"""
    poses = [fk.pose(q, t) for q, t in frames]
    out = {}
    for f in FEET:
        z = [p[f].translation.z for p in poses]
        low = min(z)
        out[f] = [v - low < 0.03 and low - floor < 0.08 for v in z]
    return out


def _gait(fk, frames, fps, floor, speed, stance=None):
    """UX's columns (round 3) for one clip as keyed: positions are armature space, z up, the rig facing -y. Ground
    speed is how fast the planted foot slides back, over the frames in stance (default: this clip's own)."""
    poses = [fk.pose(q, t) for q, t in frames]
    n = len(poses)
    stance = stance or _stance(fk, frames, floor)
    z = {k: [p[k].translation.z - floor for p in poses] for k in FEET + HEELS + ('pelvis',)}
    down = {s: [z[f][i] < 0.05 or z[h][i] < 0.13 for i in range(n)] for s, f, h in (('l', 'ball_l', 'foot_l'),
                                                                                       ('r', 'ball_r', 'foot_r'))}
    ground = _ground(poses, stance, fps)
    cycle = (n - 1) / fps
    out = {'frames': n, 'seconds': round(cycle, 3), 'ground_speed': round(ground, 3),
           'pelvis_bob': round(max(z['pelvis']) - min(z['pelvis']), 3),
           'ankle_max': round(max(max(z['foot_l']), max(z['foot_r'])), 3),
           'ball_max': round(max(max(z['ball_l']), max(z['ball_r'])), 3),
           'flight': round(sum(1 for i in range(n) if not down['l'][i] and not down['r'][i]) / n, 2),
           'lowest': round(min(min(z[f]) for f in FEET), 3)}
    if ground > 0.05:
        rate = (speed or ground) / ground
        out.update({'plays_at': speed, 'rate': round(rate, 2), 'cadence': round(2 * 60 * rate / cycle),
                    'step': round(ground * cycle / 2, 2)})
    return out


def build(rig, glb_path, fps=FPS):
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
    fk = Fk(rig, tgt_rest)
    floor = min(tgt_rest[f].translation.z for f in FEET)

    for tr in list(rig.animation_data.nla_tracks) if rig.animation_data else []:
        rig.animation_data.nla_tracks.remove(tr)
    rig.animation_data_create()
    src.animation_data_create()
    order = [b for b in tb]                       # parents come before children in Blender's bone list
    report = {}
    out = []
    means = {}
    mine = {a.name.rsplit('.', 1)[0] if a.name[-4:-3] == '.' else a.name: a for a in acts}   # Idle_Loop.001 etc.
    for clip, ual in CLIPS.items():
        sa = mine[ual]
        src.animation_data.action = sa
        if src.animation_data.action_slot is None and sa.slots:   # Blender 4.4+ slotted actions
            src.animation_data.action_slot = sa.slots[0]
        f0, f1 = (int(round(v)) for v in sa.frame_range)
        frames = []                               # per frame: ({bone: local rotation}, pelvis position)
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
            quats = {}
            for b in order:
                parent = b.parent
                ppose = pose[parent.name] if parent else Matrix.Identity(4)
                prest = tgt_rest[parent.name] if parent else Matrix.Identity(4)
                basis = (prest.inverted() @ tgt_rest[b.name]).inverted() @ ppose.inverted() @ pose[b.name]
                quats[b.name] = basis.to_quaternion()
            frames.append((quats, pose['pelvis'].translation.copy()))
        means[clip] = {b: _mean([q[b] for q, _ in frames]) for b in ('upperarm_l', 'upperarm_r')}
        stance = _stance(fk, frames, floor)
        raw = _gait(fk, frames, fps, floor, None, stance)
        st = STYLE.get(clip, {})
        if st.get('swing') or st.get('knee'):
            frames, stance = _restyle(fk, frames, st, means, floor, stance, fps)

        act = bpy.data.actions.new(clip)
        rig.animation_data.action = act
        rest_rot = tgt_rest['pelvis'].to_3x3().inverted()
        for i, (quats, pelvis) in enumerate(frames):
            for b in order:
                pb = rig.pose.bones[b.name]
                pb.rotation_mode = 'QUATERNION'
                pb.rotation_quaternion = quats[b.name]
                pb.keyframe_insert('rotation_quaternion', frame=i + 1)
            pb = rig.pose.bones['pelvis']
            pb.location = rest_rot @ (pelvis - tgt_rest['pelvis'].translation)
            pb.keyframe_insert('location', frame=i + 1)
        for pb in rig.pose.bones:
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.location = (0, 0, 0)
        track = rig.animation_data.nla_tracks.new()
        track.name = clip
        track.strips.new(clip, 1, act)
        rig.animation_data.action = None
        act.use_fake_user = True
        report[clip] = {'from': ual, **_gait(fk, frames, fps, floor, st.get('speed'), stance)}
        if st.get('swing') or st.get('knee'):
            report[clip]['before_restyle'] = raw
        out.append(act)

    src.animation_data.action = None
    for o in imported:
        bpy.data.objects.remove(o, do_unlink=True)
    for a in acts:
        bpy.data.actions.remove(a)
    scene.frame_set(1)
    return out, report


def _restyle(fk, frames, st, means, floor, stance, fps):
    """the run toned down (STYLE); returns the new frames and their stance"""
    n = len(frames)
    period = n - 1                                # the last frame repeats the first
    bones = list(frames[0][0])
    # 1. time: the feet stay on the ground longer and fly less (UAL's jog is in the air 70% of the time). Source
    #    intervals with a planted foot get st['contact'] of the loop, the rest share what is left.
    if st.get('contact'):
        down = [stance['ball_l'][i] or stance['ball_r'][i] for i in range(n)]
        planted = [down[i] and down[i + 1] for i in range(period)]
        k = sum(planted)
        dur = [st['contact'] / k if p else (1 - st['contact']) / (period - k) for p in planted]
        u = [0.0]
        for d in dur:
            u.append(u[-1] + d)
        warped, wst = [], {f: [] for f in FEET}
        for j in range(n):
            t = j / period
            i = min(period - 1, max(x for x in range(period) if u[x] <= t + 1e-12))
            a = min(1.0, max(0.0, (t - u[i]) / dur[i]))
            qa, ta = frames[i]
            qb, tb = frames[i + 1]
            warped.append(({b: _slerp(qa[b], qb[b], a) for b in bones}, ta.lerp(tb, a)))
            for f in FEET:
                wst[f].append(stance[f][i] and stance[f][i + 1] if 0 < a < 1 else stance[f][i if a < 0.5 else i + 1])
        frames, stance = warped, wst
    series = {b: [q[b] for q, _ in frames] for b in bones}
    # 2. rotations: swings around the mean, the arms in towards idle, knees from their straightest frame
    for b, k in st.get('swing', {}).items():
        qs = series[b]
        m = _mean(qs)
        target = m
        if b.startswith('upperarm') and st.get('arms_in'):
            target = m @ _part(m.inverted() @ means['idle'][b], st['arms_in'])
        series[b] = [target @ _part(m.inverted() @ q, k) for q in qs]
    for b, (k_stance, k_swing) in st.get('knee', {}).items():
        qs = series[b]
        ref = min(qs, key=lambda q: _part(q, 1).angle)
        down = stance['ball' + b[-2:]]
        series[b] = [_scale_from(ref, q, k_stance if down[i] else k_swing) for i, q in enumerate(qs)]
    for b, k in st.get('bend', {}).items():
        qs = series[b]
        ref = min(qs, key=lambda q: _part(q, 1).angle)
        series[b] = [_scale_from(ref, q, k) for q in qs]
    newq = [{b: series[b][i] for b in bones} for i in range(n)]
    pel = [t.copy() for _, t in frames]
    # 3. height: in stance the pelvis would sit where the planted foot (ball, or heel = ankle less its rest height)
    #    touches the floor; it is kept no more than st['rise'] above its lowest stance height, and the planted leg
    #    bends to reach (two-bone IK), so the body glides instead of vaulting over a stiff leg. In the air it flies a
    #    parabola between take-off and landing, as long as the flight lasts in game time (rate = speed / ground speed).
    ankle = fk.rest['foot_l'].translation.z - floor
    poses = [fk.pose(newq[i], pel[i]) for i in range(n)]
    ground = _ground(poses, stance, fps)
    rate = st['speed'] / ground if ground > 0.05 else 1.0
    pin = [None] * n
    for i in range(period):
        lows = [min(poses[i][ball].translation.z, poses[i][heel].translation.z - ankle)
                for ball, heel in zip(FEET, HEELS) if stance[ball][i]]
        if lows:
            pin[i] = pel[i].z + floor - min(lows)
    known = [i for i in range(period) if pin[i] is not None]
    if not known:
        return [(newq[i], pel[i]) for i in range(n)], stance
    top = min(pin[i] for i in known) + st.get('rise', 1.0)
    z = [min(pin[i], top) if pin[i] is not None else None for i in range(n)]
    for i in range(period):
        if z[i] is not None:
            continue
        a = max((k for k in known if k < i), default=known[-1] - period)
        b = min((k for k in known if k > i), default=known[0] + period)
        w = (i - a) / (b - a)
        fly = (b - a) / fps / rate
        z[i] = z[a % period] * (1 - w) + z[b % period] * w + 4 * (9.81 * fly * fly / 8) * w * (1 - w)
    for i in range(period):
        q = newq[i]
        lifted = Vector((pel[i].x, pel[i].y, z[i]))
        for side in ('_l', '_r'):
            cur = fk.pose(q, lifted)
            a_now = cur['foot' + side].translation
            low = min(cur['ball' + side].translation.z, a_now.z - ankle) - floor
            if pin[i] is not None and stance['ball' + side][i]:
                want = a_now + Vector((0, 0, pin[i] - z[i]))      # where the foot was, on the floor
            elif low < 0.02:
                want = a_now + Vector((0, 0, 0.02 - low))         # a swinging foot clear of the floor
            else:
                continue
            _reach(fk, q, lifted, side, want)
        pel[i] = lifted
    newq[period] = dict(newq[0])
    pel[period] = pel[0].copy()
    return [(newq[i], pel[i]) for i in range(n)], stance


def _reach(fk, quats, pelvis, side, target):
    """two-bone IK: thigh and calf bend so the ankle reaches target, in the plane the knee already points to; the foot
    keeps its orientation in armature space"""
    pose = fk.pose(quats, pelvis)
    th, ca, fo = 'thigh' + side, 'calf' + side, 'foot' + side
    hip, knee, ank = (pose[b].translation for b in (th, ca, fo))
    l1, l2 = (knee - hip).length, (ank - knee).length
    to = target - hip
    d = min(l1 + l2 - 1e-4, max(abs(l1 - l2) + 1e-4, to.length))
    axis = to.normalized()
    pole = (knee - hip) - axis * (knee - hip).dot(axis)
    if pole.length < 1e-6:
        return
    pole.normalize()
    c = max(-1.0, min(1.0, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)))
    knee2 = hip + axis * (l1 * c) + pole * (l1 * math.sqrt(1 - c * c))
    foot_rot = pose[fo].to_3x3()
    world = (knee - hip).rotation_difference(knee2 - hip).to_matrix() @ pose[th].to_3x3()
    quats[th] = ((pose['pelvis'] @ fk.rel[th]).to_3x3().inverted() @ world).to_quaternion()
    pose = fk.pose(quats, pelvis)
    k, a = pose[ca].translation, pose[fo].translation
    world = (a - k).rotation_difference(hip + axis * d - k).to_matrix() @ pose[ca].to_3x3()
    quats[ca] = ((pose[th] @ fk.rel[ca]).to_3x3().inverted() @ world).to_quaternion()
    pose = fk.pose(quats, pelvis)
    quats[fo] = ((pose[ca] @ fk.rel[fo]).to_3x3().inverted() @ foot_rot).to_quaternion()


def _slerp(a, b, t):
    if Vector(a).dot(Vector(b)) < 0:
        b = -b
    return a.slerp(b, t)


def _ground(poses, stance, fps):
    slide = []
    for f in FEET:
        for i in range(len(poses) - 1):
            if stance[f][i] and stance[f][i + 1]:
                slide.append(abs(poses[i + 1][f].translation.y - poses[i][f].translation.y) * fps)
    slide.sort()
    return slide[len(slide) // 2] if slide else 0.0
