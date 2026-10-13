// Pack the baked plaza for the page (F-2): meshopt geometry, KTX2 textures in two tiers, KTX2 lightmaps, a navmesh
// tagged by place, and scene.json (spots, places, exits, every file with its size and sha256).
// node pack_scene.mjs <work_dir> <layout.json> <out_dir> [--skip-hi]
//   work_dir: what build.sh made (plaza_raw.glb, lm_*.png, lm_meta.json, tex/ with sources.json)
// Other scenes (the road stops, F-10) run the same steps: SCENE_STEM names <stem>_raw.glb, SCENE_ROT_DEG and
// SCENE_MINUS_X_AZ are the frame the sky and the bake used, and layout.json may name its own high-tier textures.
// Tiers (frontend-design 10.6.2, ux/art-direction 9.3): std = colour 1024, normal and roughness 512;
// hi = the 5〜6 materials that fill most of the screen get colour 2048 + normal 1024, downloaded only at L2+.
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
import { buildNav } from "./nav.mjs";
import { planToWorld } from "./frame.mjs";
import { decodeKTX2, meanRGB } from "./ktx2_decode.mjs";

const [, , WORK, LAYOUT, OUT, ...flags] = process.argv;
const SKIP_HI = flags.includes("--skip-hi");
const layout = JSON.parse(fs.readFileSync(LAYOUT, "utf8"));
const ROT = layout.rotationDeg;
if (ROT !== Number(process.env.SCENE_ROT_DEG ?? 144))
  throw new Error(
    `layout rotationDeg ${ROT} but the sky and the bake were rotated by ${process.env.SCENE_ROT_DEG ?? 144}`,
  );
const STEM = process.env.SCENE_STEM ?? "plaza";
const MINUS_X_AZ = Number(process.env.SCENE_MINUS_X_AZ ?? 294);
fs.rmSync(OUT, { recursive: true, force: true });
for (const d of ["tex/std", "tex/hi", "lm"])
  fs.mkdirSync(path.join(OUT, d), { recursive: true });

const STD = { base: 1024, nrm: 512, mr: 512 };
const HI = layout.hiTextures
  ? {
      base: new Set(layout.hiTextures.base),
      nrm: new Set(layout.hiTextures.nrm),
    }
  : {
      base: new Set([
        "floor",
        "ashlar2",
        "plaster",
        "doors",
        "roofwarm",
        "plain",
      ]),
      nrm: new Set(["floor", "ashlar", "plain", "doors", "roof"]),
    };
const HI_SIZE = { base: 2048, nrm: 1024 };
const LM_RES = Number(process.env.BAKE_RES ?? 2048); // the final lightmap size (bake.py)

const io = new NodeIO()
  .registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({ "meshopt.encoder": MeshoptEncoder });
await MeshoptEncoder.ready;

const sha = (buf) => crypto.createHash("sha256").update(buf).digest("hex");
const files = [];
function put(rel, buf, pack) {
  fs.writeFileSync(path.join(OUT, rel), buf);
  files.push({ path: rel, bytes: buf.length, sha256: sha(buf), pack });
  return rel;
}
const decoder = async (buf) => {
  const { data, info } = await sharp(buf)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });
  return { data: new Uint8Array(data), width: info.width, height: info.height };
};
// one image -> KTX2. kind: 'color' (ETC1S, sRGB), 'linear' (ETC1S), 'normal' (UASTC + zstd).
// mean = average colour of the decoded result (what the phone shows), for the two-tier check in check_scene.mjs
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
  console.log = () => {}; // the Basis encoder prints every mip level
  let out;
  try {
    out = Buffer.from(await encodeToKTX2(new Uint8Array(png), opts));
  } finally {
    console.log = log;
  }
  return { buf: out, mean: meanRGB((await decodeKTX2(out)).rgba) };
}

// ---------------------------------------------------------------- geometry
const doc = await io.read(path.join(WORK, `${STEM}_raw.glb`));
const root = doc.getRoot();
const materials = {};
const used = new Map(); // texture key (e.g. floor_base) -> slot kind
const SLOT = {
  base: "getBaseColorTexture",
  nrm: "getNormalTexture",
  mr: "getMetallicRoughnessTexture",
};
for (const m of root.listMaterials()) {
  const name = m.getName();
  const e = {
    color: m.getBaseColorFactor().slice(0, 3),
    roughness: m.getRoughnessFactor(),
    metalness: m.getMetallicFactor(),
  };
  for (const [slot, getter] of Object.entries(SLOT)) {
    const t = m[getter]();
    if (!t) continue;
    e[slot] = t.getName(); // Blender keeps the image name: <key>_<kind>
    used.set(t.getName(), slot);
  }
  if (name === "proxy_mat") continue;
  materials[name] = e;
  m.setBaseColorTexture(null)
    .setNormalTexture(null)
    .setMetallicRoughnessTexture(null);
}
for (const t of root.listTextures()) t.dispose();
// Blender's exporter sorts vertices but not always triangles: two runs from the same input gave the far cypress
// primitive the same triangles in a different order. Sort each primitive's triangles (winding kept) so the same input
// packs to the same bytes (README, "Reproducibility / 再現性").
const sortedIdx = new Set();
for (const me of root.listMeshes())
  for (const p of me.listPrimitives()) {
    const acc = p.getIndices();
    if (!acc || sortedIdx.has(acc)) continue;
    sortedIdx.add(acc);
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
// the nav input comes from the uncompressed meshes
const navInput = [];
for (const n of root.listNodes()) {
  if (!["ground", "arch"].includes(n.getName())) continue;
  for (const p of n.getMesh().listPrimitives()) {
    navInput.push({
      pos: Float32Array.from(p.getAttribute("POSITION").getArray()),
      idx: Uint32Array.from(p.getIndices().getArray()), // copies: the transforms below rewrite accessors
    });
  }
}
await doc.transform(
  prune({ keepAttributes: true }),
  dedup({
    propertyTypes: [
      PropertyType.ACCESSOR,
      PropertyType.MESH,
      // not MATERIAL: with the textures stripped several materials look identical, and the page binds by name
    ],
  }),
  quantize({ quantizePosition: 16, quantizeTexcoord: 14, quantizeNormal: 10 }),
  meshopt({ encoder: MeshoptEncoder, level: "medium" }),
);
const nodes = {};
let tris = 0;
for (const n of root.listNodes()) {
  const me = n.getMesh();
  if (!me) continue;
  const t = me
    .listPrimitives()
    .reduce((s, p) => s + p.getIndices().getCount() / 3, 0);
  tris += t;
  nodes[n.getName()] = { prims: me.listPrimitives().length, tris: t };
}
put("geo.glb", Buffer.from(await io.writeBinary(doc)), "entry");
Object.assign(nodes.ground, { lightmap: "ground" });
Object.assign(nodes.arch, { lightmap: "arch" });
Object.assign(nodes.proxy, { shadowCasterOnly: true });
if (nodes.workshop_gate) {
  // open as modelled; closed = turned 90° about the hinge (the node origin); see build_plaza.py workshop()
  Object.assign(nodes.workshop_gate, {
    movable: true,
    place: "place.stonemason-workshop",
    closedYawDeg: 90,
  });
}

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
  const stem = key.slice(0, key.lastIndexOf("_"));
  const entry = {
    slot,
    from: sources[key]?.from ?? "unknown",
    sourceSha256: sha(src),
  };
  const s = await ktx2(src, STD[slot], kind);
  entry.std = {
    file: put(`tex/std/${key}.ktx2`, s.buf, "entry"),
    size: STD[slot],
    mean: s.mean,
  };
  if (!SKIP_HI && HI[slot]?.has(stem)) {
    const h = await ktx2(src, HI_SIZE[slot], kind);
    entry.hi = {
      file: put(`tex/hi/${key}.ktx2`, h.buf, "hi"),
      size: HI_SIZE[slot],
      mean: h.mean,
    };
  }
  textures[key] = entry;
  console.log(
    "tex",
    key,
    entry.std.size,
    s.buf.length,
    entry.hi ? `hi ${entry.hi.size}` : "",
  );
}

// ---------------------------------------------------------------- lightmaps (the 18:30 sunset set + ambient occlusion)
const lmMeta = JSON.parse(
  fs.readFileSync(path.join(WORK, "lm_meta.json"), "utf8"),
);
// a draft bake is 512: keep its size rather than blowing it up
const LM = Math.min(LM_RES, lmMeta.ground.res, lmMeta.arch.res);
const lightmaps = { res: LM, bakeMinute: lmMeta.bakeMinute ?? 1110 };
for (const mesh of ["ground", "arch"]) {
  const ind = await ktx2(
    fs.readFileSync(path.join(WORK, `lm_${mesh}_indirect.png`)),
    LM,
    "color",
  );
  const ao = await ktx2(
    fs.readFileSync(path.join(WORK, `lm_${mesh}_ao.png`)),
    LM,
    "linear",
  );
  lightmaps[mesh] = {
    // three.js: lightMapIntensity = PI * K (encode.py stores baked / K, sRGB-encoded)
    indirect: {
      file: put(`lm/${mesh}_indirect.ktx2`, ind.buf, "entry"),
      K: lmMeta[mesh].K_indirect,
    },
    ao: { file: put(`lm/${mesh}_ao.ktx2`, ao.buf, "entry") },
    bakedRes: lmMeta[mesh].res,
  };
}

// ---------------------------------------------------------------- navmesh, spots, places
const nav = await buildNav(navInput, layout);
put("nav.json", Buffer.from(JSON.stringify(nav.json)), "entry");
for (const w of nav.warnings) console.warn("nav:", w);
if (nav.errors.length) {
  for (const e of nav.errors) console.error("nav:", e);
  process.exit(1);
}

// ---------------------------------------------------------------- scene.json
// What this build was made from: the layout and the scripts by sha256, where each texture came from (a scan by its
// sha256), the tool versions, and the environment variables the scripts read (build.sh runs every step in one
// environment, so what this step sees is what the sky and the bake saw). check_scene.mjs compares the committed
// manifest's inputs with a fresh build's, so a pipeline change that was not followed by a new final build shows up
// in CI. Derived bytes (texture PNGs, bakes) are left out: they can differ a little between machines (README, "Reproducibility / 再現性").
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../../..");
// SCENE_INPUTS: another scene's own scripts (repo-relative, comma-separated) in place of the plaza's build.sh,
// placeholder_tex.py and build_plaza.py
const OWN = process.env.SCENE_INPUTS?.split(",").map((f) => path.join(REPO, f));
const SCRIPTS = [
  "build.sh",
  "requirements.txt",
  "placeholder_tex.py",
  "build_plaza.py",
  "sky.py",
  "sunpos.py",
  "bake.py",
  "encode.py",
  "pack_scene.mjs",
  "nav.mjs",
  "frame.mjs",
  "ktx2_decode.mjs",
];
const TOOLS = [
  "@gltf-transform/core",
  "@gltf-transform/extensions",
  "@gltf-transform/functions",
  "meshoptimizer",
  "ktx2-encoder",
  "sharp",
  "recast-navigation",
  "three",
];
// read by sky.py, sunpos.py and encode.py; unset means the default written in those scripts
const ENV = [
  "E_SKY",
  "AEROSOL",
  "SKY_W",
  "SKY_H",
  "PLAZA_BAKE_MINUTE",
  "SCENE_STEM",
  "SCENE_ROT_DEG",
  "SCENE_MINUS_X_AZ",
  "SKY_SUN_ELEV_DEG",
  "BAKE_SUN_E",
  "BAKE_SUN_RGB",
  "BAKE_RES",
];
const texSources = JSON.parse(
  fs.readFileSync(path.join(WORK, "tex/sources.json"), "utf8"),
);
const inputs = {
  files: Object.fromEntries(
    [
      path.resolve(LAYOUT),
      ...(OWN ?? []),
      ...SCRIPTS.filter(
        (f) =>
          !OWN ||
          !["build.sh", "placeholder_tex.py", "build_plaza.py"].includes(f),
      ).map((f) => path.join(HERE, f)),
    ].map((f) => [path.relative(REPO, f), sha(fs.readFileSync(f))]),
  ),
  textures: Object.fromEntries(
    Object.entries(texSources)
      .sort(([a], [b]) => (a < b ? -1 : 1))
      .map(([k, v]) => [
        k,
        v.from === "scan" ? `scan:${v.file}:${v.sha256}` : v.from,
      ]),
  ),
  tools: Object.fromEntries(
    TOOLS.map((t) => [
      t,
      JSON.parse(
        fs.readFileSync(
          path.join(HERE, "../node_modules", t, "package.json"),
          "utf8",
        ),
      ).version,
    ]),
  ),
  env: Object.fromEntries(ENV.map((k) => [k, process.env[k] ?? "default"])),
};
const sum = (pred) => files.filter(pred).reduce((s, f) => s + f.bytes, 0);
const placeholder = Object.values(textures).some((t) => t.from !== "scan");
const scene = {
  version: 1,
  sceneId: layout.sceneId,
  ...(layout.partOf ? { partOf: layout.partOf } : {}),
  note: `Generated by ${process.env.SCENE_BUILD ?? "assets/pipeline/plaza/build.sh"} from layout.json; do not edit by hand.`,
  frame: `glTF metres, +Y up. Plan (x, y) of layout.json -> rotate ${ROT}° about up -> (xr, height, -yr).`,
  quality: LM >= LM_RES ? "final" : "draft",
  placeholderTextures: placeholder,
  inputs,
  sun: {
    latitudeDeg: 37,
    declinationDeg: 19,
    solarNoonMinute: 720,
    gateStreetAzimuthDeg: MINUS_X_AZ, // the azimuth of plan −x (the gate street in the plaza)
    sceneRotationDeg: ROT,
  },
  ...(layout.ridgeElevationDeg !== undefined
    ? { ridgeElevationDeg: layout.ridgeElevationDeg }
    : {}),
  ...(layout.water ? { water: layout.water } : {}),
  nodes,
  tris,
  materials,
  textures,
  lightmaps,
  nav: {
    file: "nav.json",
    polys: nav.json.polys.length,
    agent: nav.json.agent,
  },
  defaultPlace: layout.defaultPlace,
  places: layout.places.map((p) => ({
    id: p.id,
    polygon: p.polygon
      .map(([x, y]) => planToWorld(x, y, 0, ROT))
      .map(([x, , z]) => [x, z]),
  })),
  exits: layout.exits.map(({ place, spot }) => ({ place, spot })),
  playerStartSpot: layout.playerStartSpot,
  startSpots: layout.startSpots,
  spots: nav.spots,
  files,
  bytes: {
    entry: sum((f) => f.pack === "entry"),
    hiExtra: sum((f) => f.pack === "hi"),
  },
};
scene.bytes.envStd = scene.bytes.entry;
scene.bytes.envHi = scene.bytes.entry + scene.bytes.hiExtra;
fs.writeFileSync(
  path.join(OUT, "scene.json"),
  JSON.stringify(scene, null, 1) + "\n",
);
console.log(
  `scene: ${files.length} files, entry ${(scene.bytes.entry / 1e6).toFixed(2)} MB, hi +${(scene.bytes.hiExtra / 1e6).toFixed(2)} MB, ` +
    `${tris} tris, nav ${scene.nav.polys} polys, ${Object.keys(nav.spots).length} spots`,
);
