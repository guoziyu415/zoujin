import { NodeIO, PropertyType } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { prune, dedup, quantize, meshopt, cloneDocument, textureCompress } from '@gltf-transform/functions';
import { MeshoptEncoder } from 'meshoptimizer';
import sharp from 'sharp';
import fs from 'fs';
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.encoder': MeshoptEncoder });
await MeshoptEncoder.ready;
const O = '/tmp/spk/s7out';
// plaza: strip textures (page loads them as separate files), quantize
const doc = await io.read('/tmp/spk/s7build/plaza_raw.glb');
for (const m of doc.getRoot().listMaterials()) {
  m.setBaseColorTexture(null); m.setNormalTexture(null); m.setMetallicRoughnessTexture(null); m.setOcclusionTexture(null); m.setEmissiveTexture(null);
}
for (const t of doc.getRoot().listTextures()) t.dispose();
await doc.transform(prune({ keepAttributes: true }), dedup({ propertyTypes: [PropertyType.ACCESSOR, PropertyType.MESH] }), quantize({ quantizePosition: 16, quantizeTexcoord: 14, quantizeNormal: 10 }));
await io.write(`${O}/plaza_geo.glb`, doc);
const d2 = cloneDocument(doc); await d2.transform(meshopt({ encoder: MeshoptEncoder, level: 'medium' }));
await io.write(`${O}/plaza_geo.meshopt.glb`, d2);
const stats = {};
for (const n of doc.getRoot().listNodes()) {
  const me = n.getMesh(); if (!me) continue;
  stats[n.getName()] = { prims: me.listPrimitives().length, tris: me.listPrimitives().reduce((s, p) => s + p.getIndices().getCount() / 3, 0), mats: me.listPrimitives().map(p => p.getMaterial()?.getName()) };
}
console.log(JSON.stringify(stats));
console.log('plaza_geo', fs.statSync(`${O}/plaza_geo.glb`).size, 'meshopt', fs.statSync(`${O}/plaza_geo.meshopt.glb`).size);
// characters: quantized (no wasm decoder needed in the page)
for (const tag of ['28k', '12k', '8k']) {
  const c = await io.read(`${O}/michelle_${tag}.glb`);
  await c.transform(quantize({ quantizePosition: 14, quantizeTexcoord: 12, quantizeNormal: 10, quantizeWeight: 8 }));
  await io.write(`${O}/michelle_${tag}.q.glb`, c);
  console.log('michelle', tag, 'quantized', fs.statSync(`${O}/michelle_${tag}.q.glb`).size);
}
for (const tag of ['28k', '12k', '8k']) {
  const c = await io.read(`${O}/michelle_${tag}.q.glb`);
  const r = c.getRoot();
  console.log(tag, 'skins', r.listSkins().length, 'joints', r.listSkins()[0]?.listJoints().length, 'meshes', r.listMeshes().map(m => m.getName() + ':' + m.listPrimitives().map(p => p.getAttribute('JOINTS_0') ? 'skinned' : 'static').join(',')), 'nodesWithSkin', r.listNodes().filter(n => n.getSkin()).length);
}
