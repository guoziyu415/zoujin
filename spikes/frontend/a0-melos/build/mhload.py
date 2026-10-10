"""Read the old MakeHuman data (npm makehuman-data 0.0.2, three.js JSON 3.1) with numpy.

Stand-in only: this data carries AGPL / CC-BY headers and has no ARKit face units.
The real character comes from MPFB 2 + its CC0 system assets on zg's Mac.
Units: MakeHuman decimetres, Y up.  Callers convert to Blender (metres, Z up).
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, 'mhd')
J = os.path.join(HERE, 'mhjson')


def _load(p):
    with open(p) as f:
        return json.load(f)


def decode_faces(f):
    """three.js JSON 3 face list -> list of (verts, material, uvs)."""
    out, i = [], 0
    while i < len(f):
        t = f[i]
        i += 1
        nv = 4 if t & 1 else 3
        vs = f[i:i + nv]
        i += nv
        mat = 0
        if t & 2:
            mat = f[i]
            i += 1
        if t & 4:
            i += 1
        uvs = None
        if t & 8:
            uvs = f[i:i + nv]
            i += nv
        if t & 16:
            i += 1
        if t & 32:
            i += nv
        if t & 64:
            i += 1
        if t & 128:
            i += nv
        out.append((vs, mat, uvs))
    return out


def bone_name(n):
    return n[:-len('____head')] if n.endswith('____head') else n


class Base:
    def __init__(self):
        m = _load(os.path.join(D, 'models', 'human_full_size.json'))
        self.v = np.array(m['vertices'], np.float32).reshape(-1, 3)
        self.uv = np.array(m['uvs'][0], np.float32).reshape(-1, 2)
        self.faces = decode_faces(m['faces'])
        self.mats = [x['DbgName'] for x in m['materials']]
        self.bones = [bone_name(b['name']) for b in m['bones']]
        n = m['influencesPerVertex']
        self.si = np.array(m['skinIndices'], np.int32).reshape(-1, n)
        self.sw = np.array(m['skinWeights'], np.float32).reshape(-1, n)
        self.joints = m['metadata']['joint_pos_idxs']
        tl = sorted(_load(os.path.join(J, 'targets', 'target-list.json'))['targets'])
        self._ti = {k: i for i, k in enumerate(tl)}
        self._T = np.memmap(os.path.join(D, 'targets', 'targets.bin'), dtype=np.int16,
                            mode='r').reshape(len(tl), -1)

    def target(self, name):
        row = self._T[self._ti['data/targets/' + name + '.target']]
        return row.astype(np.float32).reshape(-1, 3) * 1e-3

    def mix(self, weights):
        d = np.zeros_like(self.v)
        for k, w in weights.items():
            d += w * self.target(k)
        return d

    def joint_pos(self, v, name):
        return v[self.joints[name]].mean(0)


class Proxy:
    def __init__(self, rel):
        p = os.path.join(D, 'proxies', rel)
        if os.path.isdir(p):
            p = os.path.join(p, os.path.basename(p) + '.json')
        self.dir = os.path.dirname(p)
        m = _load(p)
        md = m['metadata']
        self.name = md.get('name')
        self.license = md.get('license')
        self.ref = np.array(md['ref_vIdxs'], np.int32)
        self.w = np.array(md['weights'], np.float32)
        self.off = np.array(md['offsets'], np.float32)
        dv = md.get('deleteVerts') or []
        self.delete = np.array([bool(x) for x in dv], bool) if len(dv) else None
        self.raw = np.array(m['vertices'], np.float32).reshape(-1, 3)
        self.uv = np.array(m['uvs'][0], np.float32).reshape(-1, 2)
        self.faces = decode_faces(m['faces'])
        self.mats = m['materials']
        n = m['influencesPerVertex']
        self.si = np.array(m['skinIndices'], np.int32).reshape(-1, n)
        self.sw = np.array(m['skinWeights'], np.float32).reshape(-1, n)

    def _interp(self, basev):
        if self.ref.ndim == 1:
            return basev[self.ref]
        return (basev[self.ref] * self.w[:, :, None]).sum(1)

    def fit(self, basev):
        """MakeHuman mhclo binding: three reference vertices, weights, offset.
        The offsets are a few millimetres; MakeHuman's per-axis offset scaling is not
        in this data and is skipped.  (The stored 'vertices' of these proxy files are
        shifted by varying amounts and are not used.)"""
        return self._interp(basev) + self.off

    def drop_transparent_faces(self, tex_path):
        """Remove faces whose texture is transparent at their UV centre (the eye's
        cornea shell maps to an alpha-0 corner of the texture)."""
        from PIL import Image
        im = np.array(Image.open(tex_path).convert('RGBA'))
        h, w = im.shape[:2]
        keep = []
        for f in self.faces:
            c = self.uv[np.array(f[2])].mean(0)
            a = im[int((1 - c[1]) * (h - 1)), int(c[0] * (w - 1)), 3]
            keep.append(a > 127)
        faces = [f for f, k in zip(self.faces, keep) if k]
        used = sorted({i for f in faces for i in f[0]})
        remap = {o: n for n, o in enumerate(used)}
        self.faces = [([remap[i] for i in f[0]], f[1], f[2]) for f in faces]
        used = np.array(used)
        self.ref, self.w, self.off = self.ref[used], self.w[used], self.off[used]
        self.si, self.sw = self.si[used], self.sw[used]
        return len(keep) - len(faces)

    def tex(self, key='mapDiffuse'):
        t = self.mats[0].get(key)
        return os.path.join(self.dir, t) if t else None


def rig():
    return _load(os.path.join(J, 'rigs', 'default.json'))
