// CI gate for the village (F-11) on top of check_scene.mjs (download budgets, tiers, navmesh, spots): its share of the
// roadside pack, draw calls, the instanced nodes.
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

console.log(rows.join("\n"));
if (errors.length) {
  console.error(`\n${errors.length} problem(s):\n- ${errors.join("\n- ")}`);
  process.exit(1);
}
console.log("ok");
