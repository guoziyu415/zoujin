"""A-0 stand-in: build a "Melos-like" MakeHuman character in Blender from the old npm data.

Run:  /tmp/bpyenv/bin/python build_standin.py  -> out/standin.blend
Stand-in only (AGPL / CC-BY data, no ARKit units).  It exists so the LOD, export,
compression and phone test page can be built and measured before the real MPFB
character is made on zg's Mac.  Same hm08 topology as MPFB, so vertex counts and
face regions match.
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mhload as L  # noqa: E402

OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- body shape
# Melos (art-direction 5.4): young shepherd, lean and long, muscular arms, tanned.
MACRO = {
    'macrodetails/universal-male-young-averagemuscle-minweight': 0.30,
    'macrodetails/universal-male-young-maxmuscle-minweight': 0.30,
    'macrodetails/universal-male-young-averagemuscle-averageweight': 0.20,
    'macrodetails/universal-male-young-maxmuscle-averageweight': 0.20,
    'macrodetails/caucasian-male-young': 0.6,
    'macrodetails/african-male-young': 0.2,
    'macrodetails/asian-male-young': 0.2,
    'macrodetails/height/male-young-averagemuscle-averageweight-maxheight': 0.35,
    'macrodetails/proportions/male-young-averagemuscle-averageweight-idealproportions': 0.7,
}

PROXIES = {  # object name -> (proxy dir, carries face shapes)
    'Eyes': ('eyes/HighPolyEyes', False),
    'EyesLow': ('eyes/Low-Poly', False),
    'Brows': ('eyebrows/eyebrow001', True),
    'Lashes': ('eyelashes/Eyelashes01', True),
    'Teeth': ('teeth/Teeth_Shape01', True),
    'Tongue': ('tongue/tongue01', True),
    'Hair': ('hair/short02', False),
    'Tunic': ('clothes/Asymmetric_Tunic_and_Sash', False),
}

# --------------------------------------------------------- face shape recipes
U = 'expression/units/caucasian/'
# ARKit 52 names -> list of (unit, amount, side) ; side: L, R, B (both), U/D (upper/lower lip)
# Built from MakeHuman's 34 expression units; the rest are approximations.  The real
# set comes from MPFB faceunits01.
ARKIT = {
    'eyeBlinkLeft': [('eye-left-closure', 1, 'B')], 'eyeBlinkRight': [('eye-right-closure', 1, 'B')],
    'eyeLookDownLeft': [('eye-left-closure', .25, 'B')], 'eyeLookDownRight': [('eye-right-closure', .25, 'B')],
    'eyeLookInLeft': [('eye-left-slit', .15, 'B')], 'eyeLookInRight': [('eye-right-slit', .15, 'B')],
    'eyeLookOutLeft': [('eye-left-slit', .15, 'B')], 'eyeLookOutRight': [('eye-right-slit', .15, 'B')],
    'eyeLookUpLeft': [('eye-left-opened-up', .35, 'B')], 'eyeLookUpRight': [('eye-right-opened-up', .35, 'B')],
    'eyeSquintLeft': [('eye-left-slit', 1, 'B')], 'eyeSquintRight': [('eye-right-slit', 1, 'B')],
    'eyeWideLeft': [('eye-left-opened-up', 1, 'B')], 'eyeWideRight': [('eye-right-opened-up', 1, 'B')],
    'jawForward': [('mouth-protusion', .3, 'B'), ('mouth-open', .1, 'B')],
    'jawLeft': [('mouth-open', .15, 'B'), ('@shift', .04, 'L')],
    'jawRight': [('mouth-open', .15, 'B'), ('@shift', .04, 'R')],
    'jawOpen': [('mouth-open', 1, 'B')],
    'mouthClose': [('mouth-compression', .5, 'B')],
    'mouthFunnel': [('mouth-protusion', 1, 'B')],
    'mouthPucker': [('mouth-pursing', 1, 'B')],
    'mouthLeft': [('@shift', .06, 'L')], 'mouthRight': [('@shift', .06, 'R')],
    'mouthSmileLeft': [('mouth-corner-puller', 1, 'L')], 'mouthSmileRight': [('mouth-corner-puller', 1, 'R')],
    'mouthFrownLeft': [('mouth-depression', 1, 'L')], 'mouthFrownRight': [('mouth-depression', 1, 'R')],
    'mouthDimpleLeft': [('mouth-retraction', .5, 'L')], 'mouthDimpleRight': [('mouth-retraction', .5, 'R')],
    'mouthStretchLeft': [('mouth-part-later', 1, 'L')], 'mouthStretchRight': [('mouth-part-later', 1, 'R')],
    'mouthRollLower': [('mouth-eversion', -1, 'D')], 'mouthRollUpper': [('mouth-eversion', -1, 'U')],
    'mouthShrugLower': [('mouth-elevation', 1, 'D')], 'mouthShrugUpper': [('mouth-elevation', 1, 'U')],
    'mouthPressLeft': [('mouth-compression', 1, 'L')], 'mouthPressRight': [('mouth-compression', 1, 'R')],
    'mouthLowerDownLeft': [('mouth-depression-retraction', 1, 'L')],
    'mouthLowerDownRight': [('mouth-depression-retraction', 1, 'R')],
    'mouthUpperUpLeft': [('mouth-upward-retraction', 1, 'L')],
    'mouthUpperUpRight': [('mouth-upward-retraction', 1, 'R')],
    'browDownLeft': [('eyebrows-left-down', 1, 'B')], 'browDownRight': [('eyebrows-right-down', 1, 'B')],
    'browInnerUp': [('eyebrows-left-inner-up', 1, 'B'), ('eyebrows-right-inner-up', 1, 'B')],
    'browOuterUpLeft': [('eyebrows-left-extern-up', 1, 'B')],
    'browOuterUpRight': [('eyebrows-right-extern-up', 1, 'B')],
    'cheekPuff': [('@cheek', 1, 'B')],
    'cheekSquintLeft': [('eye-left-slit', .4, 'B'), ('mouth-corner-puller', .3, 'L')],
    'cheekSquintRight': [('eye-right-slit', .4, 'B'), ('mouth-corner-puller', .3, 'R')],
    'noseSneerLeft': [('nose-left-elevation', 1, 'B')], 'noseSneerRight': [('nose-right-elevation', 1, 'B')],
    'tongueOut': [('@tongue', 1, 'B')],
}
# Oculus / MPFB visemes02 names.  Japanese vowels: aa I U E O, closed PP / sil.
VISEMES = {
    'viseme_sil': [('mouth-compression', .05, 'B')],
    'viseme_PP': [('mouth-compression', .8, 'B')],
    'viseme_FF': [('mouth-upward-retraction', .5, 'B'), ('mouth-open', .15, 'B')],
    'viseme_TH': [('mouth-open', .25, 'B'), ('mouth-retraction', .1, 'B')],
    'viseme_DD': [('mouth-open', .3, 'B'), ('mouth-retraction', .2, 'B')],
    'viseme_kk': [('mouth-open', .35, 'B'), ('mouth-retraction', .1, 'B')],
    'viseme_CH': [('mouth-protusion', .5, 'B'), ('mouth-open', .2, 'B')],
    'viseme_SS': [('mouth-retraction', .6, 'B'), ('mouth-open', .1, 'B')],
    'viseme_nn': [('mouth-open', .2, 'B')],
    'viseme_RR': [('mouth-pursing', .4, 'B'), ('mouth-open', .2, 'B')],
    'viseme_aa': [('mouth-open', .8, 'B'), ('mouth-parling', .3, 'B')],
    'viseme_E': [('mouth-open', .4, 'B'), ('mouth-retraction', .5, 'B')],
    'viseme_I': [('mouth-retraction', .7, 'B'), ('mouth-open', .15, 'B')],
    'viseme_O': [('mouth-open', .5, 'B'), ('mouth-protusion', .6, 'B')],
    'viseme_U': [('mouth-pursing', .8, 'B'), ('mouth-open', .1, 'B')],
}

# ------------------------------------------------------------------ rig plan
# MakeHuman default rig has 163 bones; keep a game-sized subset (~53, budget <= 60)
# and fold every other bone's weights into its nearest kept ancestor.
KEEP_SIDE = ['pelvis', 'clavicle', 'shoulder01', 'upperarm01', 'lowerarm01', 'wrist',
             'upperleg01', 'lowerleg01', 'foot', 'toe1-1'] + \
    [f'finger{i}-{j}' for i in range(1, 6) for j in (1, 2)]
KEEP = {'root', 'spine05', 'spine04', 'spine03', 'spine02', 'spine01', 'neck01', 'neck02',
        'neck03', 'head', 'jaw', 'eye.L', 'eye.R'} | \
    {f'{b}.{s}' for b in KEEP_SIDE for s in 'LR'}
# kept bones whose tail should reach the end of a folded twist child
TAIL_FROM = {'upperarm01': 'upperarm02', 'lowerarm01': 'lowerarm02',
             'upperleg01': 'upperleg02', 'lowerleg01': 'lowerleg02'}


def to_blender(v, ground):
    """MakeHuman dm, Y up -> Blender metres, Z up, feet on z=0."""
    out = np.empty_like(v)
    out[:, 0] = v[:, 0] * 0.1
    out[:, 1] = -v[:, 2] * 0.1
    out[:, 2] = (v[:, 1] - ground) * 0.1
    return out


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


class Shapes:
    def __init__(self, base, v):
        self.base, self.v = base, v
        self.cache = {}
        x = base.v[:, 0]
        self.side = {'L': smooth(-0.12, 0.12, x), 'R': 1 - smooth(-0.12, 0.12, x),
                     'B': np.ones_like(x)}
        mo = np.abs(base.target(U + 'mouth-open')).sum(1)
        mouth = mo > 0
        cy = base.v[mouth, 1].mean() if mouth.any() else 0
        # upper / lower lip split around the mouth line (MakeHuman Y up)
        lips = base.v[:, 1]
        self.side['U'] = smooth(cy - 0.05, cy + 0.05, lips)
        self.side['D'] = 1 - self.side['U']
        self.mouth_mask = np.clip(mo / max(mo.max(), 1e-6) * 3, 0, 1)
        cp = np.abs(base.target(U + 'mouth-corner-puller')).sum(1)
        self.cheek_mask = np.clip(cp / max(cp.max(), 1e-6) * 2, 0, 1)

    def unit(self, name):
        if name not in self.cache:
            self.cache[name] = self.base.target(U + name)
        return self.cache[name]

    def delta(self, recipe):
        d = np.zeros_like(self.v)
        for unit, amt, side in recipe:
            s = self.side[side][:, None]
            if unit == '@shift':
                sign = 1 if side == 'L' else -1
                d[:, 0] += sign * amt * self.mouth_mask
            elif unit == '@cheek':
                # puff: push cheeks outwards from the face centre line
                c = self.cheek_mask
                d[:, 0] += np.sign(self.base.v[:, 0]) * 0.06 * c
                d[:, 2] += 0.02 * c
            elif unit == '@tongue':
                pass  # handled on the tongue mesh
            else:
                d += amt * s * self.unit(unit)
        return d


def make_mesh(name, verts_bl, faces, uv_table, uv_idx_faces, mat_names):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts_bl.tolist(), [], faces)
    me.update()
    uvl = me.uv_layers.new(name='UVMap')
    loop_uv = []
    for f in uv_idx_faces:
        loop_uv.extend(f)
    uvs = uv_table[np.array(loop_uv)]
    uvl.data.foreach_set('uv', uvs.ravel())
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for mn in mat_names:
        me.materials.append(bpy.data.materials.get(mn))
    return ob


def image(path, non_color=False):
    img = bpy.data.images.load(path, check_existing=True)
    if non_color:
        img.colorspace_settings.name = 'Non-Color'
    return img


def material(name, base=None, normal=None, color=(1, 1, 1, 1), rough=0.6, alpha=False,
             tint=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Base Color'].default_value = color
    if base:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = image(base)
        src = t.outputs['Color']
        if tint:
            mix = nt.nodes.new('ShaderNodeMix')
            mix.data_type = 'RGBA'
            mix.blend_type = 'MULTIPLY'
            mix.inputs['Factor'].default_value = 1.0
            nt.links.new(src, mix.inputs['A'])
            mix.inputs['B'].default_value = tint
            src = mix.outputs['Result']
        nt.links.new(src, bsdf.inputs['Base Color'])
        if alpha:
            nt.links.new(t.outputs['Alpha'], bsdf.inputs['Alpha'])
    if normal:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = image(normal, True)
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(t.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    if alpha:
        try:
            m.blend_method = 'CLIP'
        except Exception:
            pass
        try:
            m.surface_render_method = 'DITHERED'
        except Exception:
            pass
    return m


def add_weights(ob, bones, si, sw, rename):
    groups = {}
    for vi in range(si.shape[0]):
        acc = {}
        for k in range(si.shape[1]):
            w = float(sw[vi, k])
            if w <= 0:
                continue
            b = rename(bones[si[vi, k]])
            acc[b] = acc.get(b, 0) + w
        tot = sum(acc.values()) or 1
        for b, w in acc.items():
            groups.setdefault(b, []).append((vi, w / tot))
    for b, items in groups.items():
        g = ob.vertex_groups.new(name=b)
        for vi, w in items:
            g.add([vi], w, 'REPLACE')


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    base = L.Base()
    v = base.v + base.mix(MACRO)

    body_faces = [f for f in base.faces if base.mats[f[1]] == 'body']
    used = sorted({i for f in body_faces for i in f[0]})
    remap = {o: n for n, o in enumerate(used)}
    ground = v[used, 1].min()
    used = np.array(used)

    # ---------------- materials
    D = L.D
    skin_tex = os.path.join(D, 'skins/young_caucasian_male/textures/young_lightskinned_male_diffuse.png')
    material('skin', skin_tex, tint=(0.66, 0.47, 0.34, 1), rough=0.55)
    proxies = {}
    for name, (rel, _) in PROXIES.items():
        proxies[name] = L.Proxy(rel)
    eye_tex = os.path.join(proxies['Eyes'].dir, 'textures/brown_eye.png')
    for n in ('Eyes', 'EyesLow'):
        print(n, 'cornea faces dropped', proxies[n].drop_transparent_faces(eye_tex))
    pm = {
        'Eyes': material('eyes', eye_tex, rough=0.12),
        'Brows': material('brows', proxies['Brows'].tex(), color=(1, 1, 1, 1), rough=0.8, alpha=True,
                          tint=(0.35, 0.25, 0.18, 1)),
        'Lashes': material('lashes', proxies['Lashes'].tex(), rough=0.8, alpha=True, tint=(0.2, 0.15, 0.1, 1)),
        'Teeth': material('teeth', proxies['Teeth'].tex(), rough=0.35),
        'Tongue': material('tongue', proxies['Tongue'].tex(), rough=0.45),
        'Hair': material('hair', proxies['Hair'].tex(), rough=0.7, alpha=True, tint=(0.45, 0.32, 0.22, 1)),
        # undyed wool / ochre (art-direction 5.4)
        'Tunic': material('tunic', None, proxies['Tunic'].tex('mapNormal'),
                          color=(0.62, 0.50, 0.36, 1), rough=0.9),
    }
    pm['EyesLow'] = pm['Eyes']

    # ---------------- body
    vb = to_blender(v[used], ground)
    faces = [[remap[i] for i in f[0]] for f in body_faces]
    body = make_mesh('Body', vb, faces, base.uv, [f[2] for f in body_faces], ['skin'])

    # ---------------- proxies
    objs = {'Body': body}
    for name, p in proxies.items():
        pv = to_blender(p.fit(v), ground)
        ob = make_mesh(name, pv, [list(f[0]) for f in p.faces], p.uv, [f[2] for f in p.faces],
                       [pm[name].name])
        objs[name] = ob

    # ---------------- armature
    r = L.rig()
    rb = r['bones']
    parent_of = {b: d['parent'] for b, d in rb.items()}

    def kept(b):
        while b is not None and b not in KEEP:
            b = parent_of.get(b)
        return b or 'root'

    arm = bpy.data.armatures.new('Rig')
    rig = bpy.data.objects.new('Rig', arm)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')

    def jp(name):
        return Vector(to_blender(base.joint_pos(v, name)[None], ground)[0])

    order = []

    def visit(b):
        order.append(b)
        for c, d in rb.items():
            if d['parent'] == b:
                visit(c)
    for b, d in rb.items():
        if d['parent'] is None:
            visit(b)
    for b in order:
        if b not in KEEP:
            continue
        d = rb[b]
        eb = arm.edit_bones.new(b)
        eb.head = jp(d['head'])
        stem = b.split('.')[0]
        tail_b = TAIL_FROM.get(stem)
        if tail_b:
            tail_b = tail_b + ('.' + b.split('.')[1] if '.' in b else '')
            eb.tail = jp(rb[tail_b]['tail'])
        else:
            eb.tail = jp(d['tail'])
        if (eb.tail - eb.head).length < 1e-4:
            eb.tail = eb.head + Vector((0, 0, 0.02))
        p = d['parent']
        if p is not None:
            eb.parent = arm.edit_bones[kept(p)]
    bpy.ops.object.mode_set(mode='OBJECT')
    print('bones kept', len(arm.bones))

    # ---------------- weights
    add_weights(body, base.bones, base.si[used], base.sw[used], kept)
    for name, p in proxies.items():
        add_weights(objs[name], base.bones, p.si, p.sw, kept)
    for ob in objs.values():
        ob.parent = rig
        mod = ob.modifiers.new('Armature', 'ARMATURE')
        mod.object = rig

    # ---------------- face shapes on body + face proxies
    sh = Shapes(base, v)
    recipes = dict(ARKIT)
    recipes.update(VISEMES)
    for name in ['Body'] + [n for n, (_, f) in PROXIES.items() if f]:
        ob = objs[name]
        ob.shape_key_add(name='Basis')
    rest_body = vb
    rest_px = {n: to_blender(proxies[n].fit(v), ground) for n, (_, f) in PROXIES.items() if f}
    tongue_tip = None
    for key, rec in recipes.items():
        d = sh.delta(rec)
        vv = v + d
        nb = to_blender(vv[used], ground)
        k = body.shape_key_add(name=key, from_mix=False)
        k.data.foreach_set('co', nb.ravel())
        for n, (_, f) in PROXIES.items():
            if not f:
                continue
            pv = to_blender(proxies[n].fit(vv), ground)
            if key == 'tongueOut' and n == 'Tongue':
                rest = rest_px[n]
                if tongue_tip is None:
                    tongue_tip = rest[:, 1].min()
                # push the front of the tongue forward (Blender -Y is the face front)
                t = np.clip((rest[:, 1] - (tongue_tip + 0.04)) / -0.04, 0, 1)
                pv = rest.copy()
                pv[:, 1] -= 0.035 * t
                pv[:, 2] -= 0.008 * t
            kk = objs[n].shape_key_add(name=key, from_mix=False)
            kk.data.foreach_set('co', pv.ravel())
    print('shape keys', len(body.data.shape_keys.key_blocks) - 1)

    # body vertices hidden by the tunic (for the standard / walk versions)
    dv = proxies['Tunic'].delete
    if dv is not None:
        g = body.vertex_groups.new(name='__under_tunic')
        idx = [remap[i] for i in np.nonzero(dv)[0] if i in remap]
        g.add(idx, 1.0, 'REPLACE')
        print('under tunic', len(idx))

    for n in ('EyesLow',):
        objs[n].hide_render = True
        objs[n].hide_set(True)

    # licences of the stand-in parts, for the record
    lic = {n: p.license for n, p in proxies.items()}
    bpy.context.scene['standin_licenses'] = str(lic)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'standin.blend'))
    tris = {n: sum(len(p.vertices) - 2 for p in o.data.polygons) for n, o in objs.items()}
    print('tris', tris, 'total (no EyesLow)', sum(t for n, t in tris.items() if n != 'EyesLow'))


if __name__ == '__main__':
    main()
