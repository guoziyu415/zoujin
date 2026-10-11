// CI gate for the village (F-11) on top of check_scene.mjs (download budgets, tiers, navmesh, spots): its share of the
// roadside pack, draw calls, the instanced nodes, the sub-packs and when each light is used.
// node check_village.mjs <road-common dir> <village dir>
// A dir holding only the manifests (the committed ones) is checked on the recorded numbers.
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { isDeepStrictEqual } from "util";
import { KEYS, SHARED, packBytes, sha, stemOf } from "../common/roadside.mjs";

const [COMMON, DIR] = process.argv.slice(2);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../../..");
const json = (f) => JSON.parse(fs.readFileSync(f, "utf8"));
const errors = [];
const rows = [];
const common = json(path.join(COMMON, "pack.json"));
const s = json(path.join(DIR, "scene.json"));
const b = json(path.join(REPO, "assets/budgets.json")).scenes[s.sceneId];
if (!b) errors.push(`${s.sceneId}: no budget in assets/budgets.json scenes`);

// the shared files: the ones road-common holds, byte for byte; every texture of a key in the table is shared
const byPath = new Map(common.files.map((f) => [f.path, f]));
for (const f of s.files.filter((x) => x.shared)) {
  const c = byPath.get(f.path);
  if (f.shared !== SHARED || !c || c.sha256 !== f.sha256 || c.bytes !== f.bytes)
    errors.push(`${f.path}: not the file ${SHARED} holds`);
  const local = path.join(COMMON, f.path);
  if (fs.existsSync(local) && sha(fs.readFileSync(local)) !== f.sha256)
    errors.push(`${SHARED} ${f.path}: sha256 differs from the manifest`);
}
for (const [k, t] of Object.entries(s.textures))
  if (KEYS.includes(stemOf(k)) !== (t.shared === SHARED))
    errors.push(`${k}: shared should be ${KEYS.includes(stemOf(k))}`);
if (!isDeepStrictEqual(s.bytes, packBytes(s)))
  errors.push("bytes: not the sum of the pack's own and shared files");

// draw calls before shadows: one per primitive, the instanced nodes one each
const prims =
  Object.values(s.nodes).reduce((n, x) => n + x.prims, 0) -
  (s.nodes.proxy?.prims ?? 0);
rows.push(`draw calls ${prims} (≤ ${b?.maxDrawCalls})`);
if (b && prims > b.maxDrawCalls)
  errors.push(`${prims} draw calls > ${b.maxDrawCalls}`);
for (const n of ["wheat", "sheaf", "vine", "sheep"])
  if (!s.nodes[n]) errors.push(`instanced node ${n} missing`);
if (!s.materials.floor)
  errors.push("no floor material (Lighting.tsx reads materials.floor)");
if (!s.nodes.proxy?.shadowCasterOnly) errors.push("no shadow proxy");
rows.push(
  `own ${(s.bytes.entry / 1e6).toFixed(2)} MB, shared ${(s.bytes.shared.entry / 1e6).toFixed(2)} MB, first visit ${(s.bytes.envStd / 1e6).toFixed(2)} MB`,
);

// the sub-packs: each pack.json beside the village's directory (the interior's is its own pipeline's, ./interior/),
// the light sub-packs' files by sha256 when present, each within its budget; when each light is used (lightSets); the
// whole village (the standard tier, every sub-pack) within villageTotalMb
const subDir = (pack) => {
  const parts = path.resolve(DIR).split(path.sep);
  parts[parts.at(-1) === "build" ? parts.length - 2 : parts.length - 1] = pack;
  return parts.join(path.sep);
};
const all = json(path.join(REPO, "assets/budgets.json")).scenes;
const known = { light: new Set(["day"]), interior: new Set() };
let interiorPrims = 0;
for (const sp of s.subPacks ?? []) {
  const mf = path.join(subDir(sp.pack), "pack.json");
  const committed = path.join(REPO, "assets/scenes", sp.pack, "pack.json");
  const file = fs.existsSync(mf) ? mf : committed;
  if (!fs.existsSync(file)) {
    errors.push(`${sp.pack}: no pack.json at ${mf}`);
    continue;
  }
  const p = json(file);
  const bytes = typeof p.bytes === "number" ? p.bytes : p.bytes.entry;
  if (bytes !== sp.bytes)
    errors.push(
      `${sp.pack}: scene.json says ${sp.bytes} bytes, its pack.json ${bytes}`,
    );
  const max = all[sp.pack]?.packMb;
  rows.push(`${sp.pack} ${(bytes / 1e6).toFixed(2)} MB (≤ ${max})`);
  if (!max) errors.push(`${sp.pack}: no budget in assets/budgets.json scenes`);
  else if (bytes > max * 1e6)
    errors.push(`${sp.pack}: ${(bytes / 1e6).toFixed(2)} MB > ${max} MB`);
  if (sp.kind === "light") {
    known.light.add(p.light);
    const sum = p.files.reduce((n, f) => n + f.bytes, 0);
    if (sum !== bytes) errors.push(`${sp.pack}: bytes ${bytes}, files ${sum}`);
    for (const f of p.files) {
      const local = path.join(path.dirname(mf), f.path);
      if (fs.existsSync(local) && sha(fs.readFileSync(local)) !== f.sha256)
        errors.push(`${sp.pack} ${f.path}: sha256 differs from pack.json`);
    }
    if (p.lightmaps.res !== s.lightmaps.res)
      errors.push(
        `${sp.pack}: lightmaps ${p.lightmaps.res}, the village's ${s.lightmaps.res}`,
      );
  } else {
    for (const k of Object.keys(p.lightSets ?? {})) known.interior.add(k);
    interiorPrims += p.prims ?? 0;
  }
}
for (const id of ["sunset", "night", "rain"])
  if (!known.light.has(id)) errors.push(`no light sub-pack ${id}`);
const L = s.lightSets;
if (!L) errors.push("no lightSets (layout.json)");
for (const row of [...(L?.clear ?? []), L?.rain].filter(Boolean)) {
  for (const id of [row.outdoor].flat())
    if (!known.light.has(id)) errors.push(`lightSets: no outdoor light ${id}`);
  if (known.interior.size && !known.interior.has(row.indoor))
    errors.push(`lightSets: no indoor light ${row.indoor}`);
}
rows.push(
  `draw calls with the interior ${prims + interiorPrims} (≤ ${b?.maxDrawCalls})`,
);
if (b && prims + interiorPrims > b.maxDrawCalls)
  errors.push(
    `${prims + interiorPrims} draw calls with the interior > ${b.maxDrawCalls}`,
  );
// the high tier's extra is the strong phones' optional download, reported beside it
const whole = s.bytes.envStd + (s.subPackBytes ?? 0);
const hiExtra = s.bytes.envHi - s.bytes.envStd;
rows.push(
  `the whole village ${(whole / 1e6).toFixed(2)} MB (≤ ${b?.villageTotalMb}), with the high tier ${((whole + hiExtra) / 1e6).toFixed(2)} MB`,
);
if (b?.villageTotalMb && whole > b.villageTotalMb * 1e6)
  errors.push(
    `the whole village ${(whole / 1e6).toFixed(2)} MB > ${b.villageTotalMb} MB`,
  );

console.log(rows.join("\n"));
if (errors.length) {
  console.error(`\n${errors.length} problem(s):\n- ${errors.join("\n- ")}`);
  process.exit(1);
}
console.log("ok");
