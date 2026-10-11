// CI gate for the road's river on top of check_scene.mjs (which checks each pack on its own): the shared roadside
// pack, draw calls per pack, and scene.road-river's index and merged layout agreeing with the packs and the world
// models (F-10 acceptance).
// node check_road.mjs <road-common dir> <calm dir> <flood dir> <road-river dir>
// A dir holding only the manifests (the committed ones) is checked on the recorded numbers.
import crypto from "crypto";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { isDeepStrictEqual } from "util";

const [COMMON, ...rest] = process.argv.slice(2);
const RIVER = rest.pop();
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../../..");
const json = (f) => JSON.parse(fs.readFileSync(f, "utf8"));
const budgets = json(path.join(REPO, "assets/budgets.json")).scenes;
const errors = [];
const rows = [];
const MB = 1e6;
const limit = (label, bytes, maxMb) => {
  rows.push(
    `${label.padEnd(40)} ${(bytes / MB).toFixed(2).padStart(6)} MB  (≤ ${maxMb})`,
  );
  if (bytes > maxMb * MB)
    errors.push(`${label}: ${(bytes / MB).toFixed(2)} MB > ${maxMb} MB`);
};
const sha = (b) => crypto.createHash("sha256").update(b).digest("hex");

// ---- road-common
const common = json(path.join(COMMON, "pack.json"));
const present = common.files.every((f) =>
  fs.existsSync(path.join(COMMON, f.path)),
);
if (present)
  for (const f of common.files)
    if (sha(fs.readFileSync(path.join(COMMON, f.path))) !== f.sha256)
      errors.push(`road-common ${f.path}: sha256 differs from pack.json`);
limit("road-common", common.bytes.entry, budgets["road-common"].entryPackMb);
limit(
  "road-common with the high tier",
  common.bytes.entry + common.bytes.hiExtra,
  budgets["road-common"].envTotalHighMb,
);

// ---- the packs
const packs = rest.map((d) => ({
  dir: d,
  scene: json(path.join(d, "scene.json")),
}));
const byPath = new Map(common.files.map((f) => [f.path, f]));
for (const { scene: s } of packs) {
  const b = budgets[s.sceneId];
  if (!b) {
    errors.push(`${s.sceneId}: no budget in assets/budgets.json scenes`);
    continue;
  }
  const layout = json(
    path.join(REPO, "assets/scenes", s.sceneId, "layout.json"),
  );
  for (const f of s.files.filter((x) => x.shared)) {
    const c = byPath.get(f.path);
    if (
      f.shared !== common.pack ||
      !c ||
      c.sha256 !== f.sha256 ||
      c.bytes !== f.bytes
    )
      errors.push(`${s.sceneId} ${f.path}: not the file road-common holds`);
  }
  if (!isDeepStrictEqual(s.bytes.shared, common.bytes))
    errors.push(`${s.sceneId}: bytes.shared differs from road-common`);
  // draw calls before shadows: one per primitive (the water node is one, the page's shader replaces its material)
  const prims =
    Object.values(s.nodes).reduce((n, x) => n + x.prims, 0) -
    (s.nodes.proxy?.prims ?? 0);
  rows.push(
    `${`${s.sceneId} draw calls`.padEnd(40)} ${String(prims).padStart(6)}     (≤ ${b.maxDrawCalls})`,
  );
  if (prims > b.maxDrawCalls)
    errors.push(`${s.sceneId}: ${prims} draw calls > ${b.maxDrawCalls}`);
  if (!s.water || !s.nodes[s.water.node])
    errors.push(`${s.sceneId}: water node ${s.water?.node} missing`);
  if (
    !isDeepStrictEqual(s.water, layout.water) ||
    s.ridgeElevationDeg !== layout.ridgeElevationDeg
  )
    errors.push(
      `${s.sceneId}: water or ridge differs from layout.json (rebuild)`,
    );
  if (!s.materials.floor)
    errors.push(
      `${s.sceneId}: no floor material (Lighting.tsx reads materials.floor)`,
    );
  if (!s.nodes.proxy?.shadowCasterOnly)
    errors.push(`${s.sceneId}: no shadow proxy`);
}

// ---- scene.road-river: index and merged layout
const index = json(path.join(RIVER, "index.json"));
const merged = json(path.join(RIVER, "scene.json"));
const SCENE_ID = merged.sceneId;
if (index.sceneId !== SCENE_ID)
  errors.push("index.json and scene.json name different scenes");
for (const { scene: s } of packs) {
  if (s.partOf !== SCENE_ID)
    errors.push(`${s.sceneId}: partOf ${s.partOf}, not ${SCENE_ID}`);
  const e = index.packs.find((p) => p.pack === s.sceneId);
  const layout = json(
    path.join(REPO, "assets/scenes", s.sceneId, "layout.json"),
  );
  if (!e || e.act !== layout.select.act || e.bridge !== layout.select.bridge)
    errors.push(
      `index.json: ${s.sceneId} missing or not as its layout's select`,
    );
  if (e && !fs.existsSync(path.join(REPO, "assets/scenes", e.pack)))
    errors.push(`index.json: ${e.manifest} has no pack directory`);
  for (const [name, sp] of Object.entries(s.spots)) {
    const m = merged.spots[name];
    if (
      !m ||
      m.place !== sp.place ||
      (m.auto === false) !== (sp.auto === false) ||
      !m.packs.includes(s.sceneId)
    )
      errors.push(`merged scene.json: spot ${name} not as in ${s.sceneId}`);
  }
  for (const x of s.exits)
    if (!merged.exits.some((y) => y.place === x.place && y.spot === x.spot))
      errors.push(`merged scene.json: exit to ${x.place} missing`);
  if (
    !isDeepStrictEqual(merged.startSpotsByAct[layout.select.act], s.startSpots)
  )
    errors.push(
      `merged scene.json: startSpotsByAct ${layout.select.act} is not ${s.sceneId}'s`,
    );
}
for (const [name, m] of Object.entries(merged.spots))
  for (const p of m.packs)
    if (!packs.find((x) => x.scene.sceneId === p)?.scene.spots[name])
      errors.push(`merged scene.json: spot ${name} says it is in ${p}`);
if (new Set(index.packs.map((p) => p.act)).size !== index.packs.length)
  errors.push("index.json: two packs for the same act");

// every act of a world model that has this scene picks exactly one pack (the page goes by act)
const subdirs = (d) =>
  fs.existsSync(d)
    ? fs
        .readdirSync(d, { withFileTypes: true })
        .filter((e) => e.isDirectory())
        .map((e) => path.join(d, e.name))
    : [];
let usedBy = 0;
for (const f of subdirs(path.join(REPO, "worlds"))
  .flatMap(subdirs)
  .map((d) => path.join(d, "world.json"))
  .filter((f) => fs.existsSync(f))) {
  const w = json(f);
  const acts = (w.acts ?? []).filter((a) => a.scenes?.includes(SCENE_ID));
  if (!acts.length) continue;
  usedBy++;
  for (const a of acts) {
    const n = index.packs.filter((p) => p.act === a.id).length;
    if (n !== 1)
      errors.push(
        `${path.relative(REPO, f)}: ${a.id} has ${SCENE_ID} but index.json picks ${n} packs for it`,
      );
  }
}
rows.push(`world models with ${SCENE_ID} in their acts: ${usedBy}`);
if (!usedBy) errors.push(`no world model in worlds/ has ${SCENE_ID} in an act`);

console.log(rows.join("\n"));
if (errors.length) {
  console.error(`\n${errors.length} problem(s):\n- ${errors.join("\n- ")}`);
  process.exit(1);
}
console.log("ok");
