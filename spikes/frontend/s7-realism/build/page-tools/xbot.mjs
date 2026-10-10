// S7 character stand-in: the Mixamo X Bot mannequin (single skeleton, 2 materials), three LODs + its own clips
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { simplify, weld, prune, dedup, cloneDocument, meshopt, quantize, compactPrimitive } from '@gltf-transform/functions';
import { MeshoptSimplifier, MeshoptEncoder } from 'meshoptimizer';
import fs from 'fs';
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.encoder': MeshoptEncoder });
await MeshoptSimplifier.ready; await MeshoptEncoder.ready;
const O = '/tmp/spk/s7out';
const tris = (doc) => doc.getRoot().listMeshes().reduce((s, m) => s + m.listPrimitives().reduce((t, p) => t + p.getIndices().getCount() / 3, 0), 0);
const KEEP = ['idle', 'walk'];

const base = await io.read('/tmp/spk/assets/Xbot.glb');
const anims = cloneDocument(base);
const dropAnim = (a) => { for (const s of a.listSamplers()) { s.getInput()?.dispose(); s.getOutput()?.dispose(); s.dispose(); } for (const c of a.listChannels()) c.dispose(); a.dispose(); };
for (const a of base.getRoot().listAnimations()) dropAnim(a);
await base.transform(prune(), dedup(), weld({}));
for (const [tag, target] of [['28k', 28000], ['12k', 12000], ['8k', 8000]]) {
  const doc = cloneDocument(base);
  await doc.transform(simplify({ simplifier: MeshoptSimplifier, ratio: target / tris(doc), error: 0.03, lockBorder: false }));
  for (const m of doc.getRoot().listMeshes()) for (const p of m.listPrimitives()) compactPrimitive(p);
  await doc.transform(prune());
  await doc.transform(quantize({ quantizePosition: 14, quantizeNormal: 10, quantizeWeight: 8 }));
  for (const a of doc.getRoot().listAccessors()) if (a.listParents().every((p) => p.propertyType === 'Root')) a.dispose();   // orphans left by the removed clips
  await io.write(`${O}/person_${tag}.q.glb`, doc);
  const d2 = cloneDocument(doc); await d2.transform(meshopt({ encoder: MeshoptEncoder, level: 'medium' }));
  await io.write(`${O}/person_${tag}.meshopt.glb`, d2);
  const r = doc.getRoot();
  console.log('person', tag, Math.round(tris(doc)), 'tris; q', fs.statSync(`${O}/person_${tag}.q.glb`).size, 'B; meshopt', fs.statSync(`${O}/person_${tag}.meshopt.glb`).size, 'B; skins', r.listSkins().length, 'prims', r.listMeshes().map((m) => m.listPrimitives().length));
}
for (const a of anims.getRoot().listAnimations()) {
  if (!KEEP.includes(a.getName())) { dropAnim(a); continue; }
  // rotations only, plus the hips' translation for the walk bob
  for (const c of a.listChannels()) if (c.getTargetPath() === 'scale' || (c.getTargetPath() === 'translation' && !/Hips$/.test(c.getTargetNode().getName()))) { const sm = c.getSampler(); sm.getInput()?.listParents().length <= 2 && sm.getInput().dispose(); sm.getOutput()?.dispose(); sm.dispose(); c.dispose(); }
}
for (const n of anims.getRoot().listNodes()) { if (n.getMesh()) n.setMesh(null); if (n.getSkin()) n.setSkin(null); }
for (const m of anims.getRoot().listMeshes()) m.dispose();
for (const s of anims.getRoot().listSkins()) s.dispose();
await anims.transform(prune({ keepLeaves: true }));
for (const a of anims.getRoot().listAccessors()) if (a.listParents().every((p) => p.propertyType === 'Root')) a.dispose();
await io.write(`${O}/anims.glb`, anims);
console.log('anims', fs.statSync(`${O}/anims.glb`).size, 'B', anims.getRoot().listAnimations().map((a) => `${a.getName()} ${a.listChannels().length}ch`));
