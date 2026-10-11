// The village's instanced things (F-11 card 3): wheat, sheaves, vines and sheep, one draw call each. Run between the
// bake and pack_scene.mjs: build_village.py wrote the prototypes (<stem>_proto.glb, each at the origin) and where the
// copies stand (<stem>_inst.json, plan x, y, z, rotation about up, scale); this adds one node per prototype to the
// baked <stem>_raw.glb with EXT_mesh_gpu_instancing (three.js's GLTFLoader makes it an InstancedMesh), and a little
// colour per copy (_COLOR_0, three's instanceColor), from a hash of the prototype and the copy's number, so the same
// input gives the same bytes. The copies are not baked: in the bake they stood as occluders only.
// node merge_inst.mjs <work dir> <stem>
import { NodeIO } from "@gltf-transform/core";
import {
  ALL_EXTENSIONS,
  EXTMeshGPUInstancing,
} from "@gltf-transform/extensions";
import { mergeDocuments } from "@gltf-transform/functions";
import crypto from "crypto";
import fs from "fs";
import path from "path";

const [WORK, STEM] = process.argv.slice(2);
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const rawPath = path.join(WORK, `${STEM}_raw.glb`);
const doc = await io.read(rawPath);
const protos = await io.read(path.join(WORK, `${STEM}_proto.glb`));
const { instances } = JSON.parse(
  fs.readFileSync(path.join(WORK, `${STEM}_inst.json`), "utf8"),
);

// how much each copy may differ: [brightness, warm-cool] spread
const TINT = {
  wheat: [0.16, 0.06],
  sheaf: [0.12, 0.04],
  vine: [0.14, 0.05],
  sheep: [0.22, 0.04],
};
const unit = (s) =>
  crypto.createHash("sha256").update(s).digest().readUInt32BE(0) / 2 ** 32;

const root = doc.getRoot();
const scene = root.getDefaultScene() ?? root.listScenes()[0];
const before = new Set(root.listScenes());
mergeDocuments(doc, protos);
for (const s of root.listScenes()) {
  if (before.has(s)) continue;
  for (const n of s.listChildren()) {
    s.removeChild(n);
    scene.addChild(n);
  }
  s.dispose();
}
const ext = doc.createExtension(EXTMeshGPUInstancing).setRequired(true);
const buffer = root.listBuffers()[0];
let copies = 0;
for (const [name, rows] of Object.entries(instances).sort()) {
  const node = scene.listChildren().find((n) => n.getName() === name);
  if (!node || !node.getMesh()) throw new Error(`prototype ${name} missing`);
  const t = new Float32Array(rows.length * 3);
  const r = new Float32Array(rows.length * 4);
  const sc = new Float32Array(rows.length * 3);
  const c = new Float32Array(rows.length * 3);
  const [db, dw] = TINT[name] ?? [0.1, 0.03];
  rows.forEach(([x, y, z, rot, s], i) => {
    // plan (x, y, z) -> glTF (x, z, -y); a turn about plan up is the same turn about glTF +Y
    t.set([x, z, -y], 3 * i);
    r.set([0, Math.sin(rot / 2), 0, Math.cos(rot / 2)], 4 * i);
    sc.set([s, s, s], 3 * i);
    const b = 1 + db * (unit(`${name}:${i}:b`) - 0.5) * 2;
    const w = dw * (unit(`${name}:${i}:w`) - 0.5) * 2;
    c.set([b * (1 + w), b, b * (1 - w)], 3 * i);
  });
  const acc = (arr, type) =>
    doc.createAccessor().setType(type).setArray(arr).setBuffer(buffer);
  node.setTranslation([0, 0, 0]).setRotation([0, 0, 0, 1]).setScale([1, 1, 1]);
  node.setExtension(
    "EXT_mesh_gpu_instancing",
    ext
      .createInstancedMesh()
      .setAttribute("TRANSLATION", acc(t, "VEC3"))
      .setAttribute("ROTATION", acc(r, "VEC4"))
      .setAttribute("SCALE", acc(sc, "VEC3"))
      .setAttribute("_COLOR_0", acc(c, "VEC3")),
  );
  copies += rows.length;
  console.log(`instanced ${name}: ${rows.length} copies`);
}
// the merged document brought its own buffer: one buffer for the GLB
for (const b of root.listBuffers().slice(1)) {
  for (const a of root.listAccessors())
    if (a.getBuffer() === b) a.setBuffer(buffer);
  b.dispose();
}
fs.writeFileSync(rawPath, await io.writeBinary(doc));
console.log(
  `merged ${Object.keys(instances).length} instanced nodes, ${copies} copies, into ${STEM}_raw.glb`,
);
