// Pack the room inside Melos's house (interior.py's output) as the village's sub-pack village-interior (F-11 range 1):
// interior.glb (meshopt, textures stripped and bound by material name as the scene packs are), KTX2 textures, the two
// light sets' lightmaps, and pack.json (not scene.json: the backend reads every assets/scenes/*/scene.json as a layout).
//   node pack_interior.mjs <work_dir> <out_dir>
// pack.json: the materials and textures in scene.json's shape (the page's loadScene builds them the same way), the
// room's box in glTF coordinates (inside it the sky's light gives way to the room's, shaderPatches HALL), and per light
// set its lightmap, K (three.js lightMapIntensity = PI * K) and the floor's light at a few points (for the people).
import { NodeIO, PropertyType } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { prune, dedup, quantize, meshopt } from "@gltf-transform/functions";
import { MeshoptEncoder } from "meshoptimizer";
import { encodeToKTX2 } from "ktx2-encoder";
import sharp from "sharp";
import crypto from "crypto";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { decodeKTX2, meanRGB } from "../../plaza/ktx2_decode.mjs";

const [, , WORK, OUT] = process.argv;
fs.rmSync(OUT, { recursive: true, force: true });
for (const d of ["tex", "lm"])
  fs.mkdirSync(path.join(OUT, d), { recursive: true });
const SIZE = { base: 512, nrm: 256, mr: 256 }; // a room of 11 x 4.6 m seen from close: one tier

const sha = (buf) => crypto.createHash("sha256").update(buf).digest("hex");
const files = [];
function put(rel, buf) {
  fs.writeFileSync(path.join(OUT, rel), buf);
  files.push({ path: rel, bytes: buf.length, sha256: sha(buf) });
  return rel;
}
const decoder = async (buf) => {
  const { data, info } = await sharp(buf)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });
  return { data: new Uint8Array(data), width: info.width, height: info.height };
};
// as ../../plaza/pack_scene.mjs ktx2(): 'color' (ETC1S sRGB), 'linear' (ETC1S), 'normal' (UASTC + zstd)
async function ktx2(src, size, kind) {
  const png = await sharp(src)
    .resize(size, size, { kernel: "lanczos3", fit: "fill" })
    .png()
    .toBuffer();
  const opts =
    kind === "normal"
      ? {
          isUASTC: true,
          needSupercompression: true,
          generateMipmap: true,
          isNormalMap: true,
          imageDecoder: decoder,
        }
      : {
          isUASTC: false,
          generateMipmap: true,
          qualityLevel: 160,
          compressionLevel: 2,
          isSetKTX2SRGBTransferFunc: kind === "color",
          imageDecoder: decoder,
        };
  const log = console.log;
  console.log = () => {};
  let out;
  try {
    out = Buffer.from(await encodeToKTX2(new Uint8Array(png), opts));
  } finally {
    console.log = log;
  }
  return { buf: out, mean: meanRGB((await decodeKTX2(out)).rgba) };
}

// ---------------------------------------------------------------- geometry
const io = new NodeIO()
  .registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({ "meshopt.encoder": MeshoptEncoder });
await MeshoptEncoder.ready;
const doc = await io.read(path.join(WORK, "interior_raw.glb"));
const root = doc.getRoot();
const SLOT = {
  base: "getBaseColorTexture",
  nrm: "getNormalTexture",
  mr: "getMetallicRoughnessTexture",
};
const materials = {};
const used = new Map();
for (const m of root.listMaterials()) {
  const e = {
    color: m.getBaseColorFactor().slice(0, 3),
    roughness: m.getRoughnessFactor(),
    metalness: m.getMetallicFactor(),
  };
  for (const [slot, getter] of Object.entries(SLOT)) {
    const t = m[getter]();
    if (!t) continue;
    e[slot] = t.getName();
    used.set(t.getName(), slot);
  }
  materials[m.getName()] = e;
  m.setBaseColorTexture(null)
    .setNormalTexture(null)
    .setMetallicRoughnessTexture(null);
}
for (const t of root.listTextures()) t.dispose();
// same input, same bytes: sort each primitive's triangles (winding kept), as pack_scene.mjs does
for (const me of root.listMeshes())
  for (const p of me.listPrimitives()) {
    const acc = p.getIndices();
    const a = acc.getArray();
    const tri = [];
    for (let i = 0; i < a.length; i += 3) {
      const [x, y, z] = [a[i], a[i + 1], a[i + 2]];
      tri.push(x <= y && x <= z ? [x, y, z] : y <= z ? [y, z, x] : [z, x, y]);
    }
    tri.sort((u, v) => u[0] - v[0] || u[1] - v[1] || u[2] - v[2]);
    tri.forEach((t, k) => a.set(t, 3 * k));
    acc.setArray(a);
  }
await doc.transform(
  prune({ keepAttributes: true }),
  dedup({ propertyTypes: [PropertyType.ACCESSOR, PropertyType.MESH] }),
  quantize({ quantizePosition: 16, quantizeTexcoord: 14, quantizeNormal: 10 }),
  meshopt({ encoder: MeshoptEncoder, level: "medium" }),
);
let tris = 0;
let prims = 0;
for (const me of root.listMeshes())
  for (const p of me.listPrimitives()) {
    tris += p.getIndices().getCount() / 3;
    prims++;
  }
put("interior.glb", Buffer.from(await io.writeBinary(doc)));

// ---------------------------------------------------------------- textures
const sources = JSON.parse(
  fs.readFileSync(path.join(WORK, "tex", "sources.json"), "utf8"),
);
const textures = {};
for (const [key, slot] of [...used].sort()) {
  const file = fs
    .readdirSync(path.join(WORK, "tex"))
    .find((f) => f.startsWith(key + "."));
  if (!file) throw new Error(`texture ${key} missing in ${WORK}/tex`);
  const src = fs.readFileSync(path.join(WORK, "tex", file));
  const kind = slot === "base" ? "color" : slot === "nrm" ? "normal" : "linear";
  const s = await ktx2(src, SIZE[slot], kind);
  textures[key] = {
    slot,
    from: sources[key]?.from ?? "unknown",
    sourceSha256: sha(src),
    std: { file: put(`tex/${key}.ktx2`, s.buf), size: SIZE[slot], mean: s.mean },
  };
}

// ---------------------------------------------------------------- the light sets
const meta = JSON.parse(
  fs.readFileSync(path.join(WORK, "lm_meta.json"), "utf8"),
);
const toGltf = ([x, y], z = 0) => [x, z, -y]; // plan -> glTF (no rotation, +Y up)
const lightSets = {};
for (const [name, s] of Object.entries(meta.sets).sort()) {
  const k = await ktx2(
    fs.readFileSync(path.join(WORK, `lm_${name}.png`)),
    meta.res,
    "color",
  );
  lightSets[name] = {
    file: put(`lm/${name}.ktx2`, k.buf),
    K: s.K,
    floor: Object.fromEntries(
      Object.entries(s.floor).map(([id, p]) => [
        id,
        { pos: toGltf(p.at), rgb: p.rgb },
      ]),
    ),
  };
}
const [x0, y0, x1, y1, h] = meta.room; // plan bounds and the roof's high side
const room = { min: [x0, 0, -y1], max: [x1, h, -y0] };

// ---------------------------------------------------------------- pack.json
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../../../..");
const SCRIPTS = [
  "village/interior/build.sh",
  "village/interior/interior.py",
  "village/interior/pack_interior.mjs",
  "common/bl.py",
  "plaza/placeholder_tex.py",
  "plaza/sky.py",
  "plaza/sunpos.py",
  "plaza/ktx2_decode.mjs",
];
const TOOLS = [
  "@gltf-transform/core",
  "@gltf-transform/functions",
  "meshoptimizer",
  "ktx2-encoder",
  "sharp",
];
const ENV = ["E_SKY", "PLAZA_BAKE_MINUTE", "SCENE_ROT_DEG", "SCENE_MINUS_X_AZ"];
const pipeline = path.resolve(HERE, "../..");
const pack = {
  packId: "village-interior",
  partOf: "scene.village",
  note: "Generated by assets/pipeline/village/interior/build.sh; do not edit by hand.",
  frame:
    "glTF metres, +Y up. Plan (x, y) of the village's layout.json -> (x, height, -y) (no rotation).",
  geometry: "interior.glb",
  tris,
  prims,
  room,
  // the feast's flames (the hearth, then the lamps): glTF position of the flame's foot and its height
  flames: meta.flames.map(([x, y, z, size]) => ({ pos: toGltf([x, y], z), size })),
  lightmapRes: meta.res,
  lightSets,
  materials,
  textures,
  bytes: files.reduce((s, f) => s + f.bytes, 0),
  files,
  inputs: {
    files: Object.fromEntries(
      SCRIPTS.map((f) => [
        path.relative(REPO, path.join(pipeline, f)),
        sha(fs.readFileSync(path.join(pipeline, f))),
      ]),
    ),
    textures: Object.fromEntries(
      [...used.keys()].sort().map((k) => [k, sources[k]?.from ?? "unknown"]),
    ),
    tools: Object.fromEntries(
      TOOLS.map((t) => [
        t,
        JSON.parse(
          fs.readFileSync(
            path.join(pipeline, "node_modules", t, "package.json"),
            "utf8",
          ),
        ).version,
      ]),
    ),
    env: Object.fromEntries(ENV.map((k) => [k, process.env[k] ?? "default"])),
  },
};
fs.writeFileSync(
  path.join(OUT, "pack.json"),
  JSON.stringify(pack, null, 1) + "\n",
);
console.log(
  `village-interior: ${tris} tris in ${prims} primitives, ${(pack.bytes / 1e6).toFixed(2)} MB, ` +
    Object.entries(lightSets)
      .map(([n, s]) => `${n} K ${s.K}`)
      .join(", "),
);
