// CI gate for the road's other stops on top of check_scene.mjs (which checks each pack on its own): the shared
// roadside pack, draw calls per pack, run segments, and each scene's index and merged layout agreeing with the packs
// and the world models (F-15 acceptance; the river has check_road.mjs).
// node check_rest.mjs <road-common dir> <scene dir template> <pack dir>...
//   scene dir template: where a scene's index.json and scene.json are, {} = its folder name (road-pass ...)
// A dir holding only the manifests (the committed ones) is checked on the recorded numbers.
import crypto from "crypto";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { isDeepStrictEqual } from "util";
import { packBytes } from "../common/roadside.mjs";

const [COMMON, SCENE_DIR, ...rest] = process.argv.slice(2);
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
  // only the shared files this pack uses count for it (../common/roadside.mjs)
  if (!isDeepStrictEqual(s.bytes, packBytes(s)))
    errors.push(
      `${s.sceneId}: bytes are not the sum of its own and its shared files`,
    );
  // draw calls before shadows: one per primitive (the water node is one, the page's shader replaces its material)
  const prims =
    Object.values(s.nodes).reduce((n, x) => n + x.prims, 0) -
    (s.nodes.proxy?.prims ?? 0);
  rows.push(
    `${`${s.sceneId} draw calls`.padEnd(40)} ${String(prims).padStart(6)}     (≤ ${b.maxDrawCalls})`,
  );
  if (prims > b.maxDrawCalls)
    errors.push(`${s.sceneId}: ${prims} draw calls > ${b.maxDrawCalls}`);
  if (layout.water && !s.nodes[s.water?.node])
    errors.push(`${s.sceneId}: water node ${s.water?.node} missing`);
  if (!isDeepStrictEqual(s.runway, layout.runway))
    errors.push(`${s.sceneId}: runway differs from layout.json (rebuild)`);
  for (const name of Object.keys(layout.runway?.setPieces ?? {}))
    if (!s.nodes[`set_${name}`])
      errors.push(`${s.sceneId}: set piece set_${name} has no node`);
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

// ---- each road scene: index and merged layout
const subdirs = (d) =>
  fs.existsSync(d)
    ? fs
        .readdirSync(d, { withFileTypes: true })
        .filter((e) => e.isDirectory())
        .map((e) => path.join(d, e.name))
    : [];
const worlds = subdirs(path.join(REPO, "worlds"))
  .flatMap(subdirs)
  .map((d) => path.join(d, "world.json"))
  .filter((f) => fs.existsSync(f))
  .map((f) => ({ f, w: json(f) }));
const layoutOf = (id) =>
  json(path.join(REPO, "assets/scenes", id, "layout.json"));
const sceneIds = [
  ...new Set(packs.map((p) => p.scene.partOf).filter(Boolean)),
].sort();
for (const SCENE_ID of sceneIds) {
  const dir = SCENE_DIR.replace("{}", SCENE_ID.replace(/^scene\./, ""));
  const index = json(path.join(dir, "index.json"));
  const merged = json(path.join(dir, "scene.json"));
  if (index.sceneId !== SCENE_ID || merged.sceneId !== SCENE_ID)
    errors.push(`${dir}: index.json or scene.json names another scene`);
  for (const e of index.packs) {
    const layout = layoutOf(e.pack);
    // the scene's own packs (the field road's is itself a run segment), or a run segment standing in for it
    const ok =
      !!e.runway === !!layout.runway &&
      (layout.partOf === SCENE_ID
        ? layout.select.act === e.act && layout.select.bridge === e.bridge
        : layout.standsIn?.act === e.act &&
          layout.standsIn.scenes.includes(SCENE_ID));
    if (!ok) errors.push(`${SCENE_ID} index.json: ${e.pack} not as its layout`);
    if (!fs.existsSync(path.join(REPO, "assets/scenes", e.pack)))
      errors.push(
        `${SCENE_ID} index.json: ${e.manifest} has no pack directory`,
      );
  }
  for (const { scene: s } of packs.filter((p) => p.scene.partOf === SCENE_ID)) {
    const layout = layoutOf(s.sceneId);
    if (!index.packs.some((p) => p.pack === s.sceneId))
      errors.push(`${SCENE_ID} index.json: ${s.sceneId} missing`);
    for (const [name, sp] of Object.entries(s.spots)) {
      const m = merged.spots[name];
      if (
        !m ||
        m.place !== sp.place ||
        (m.auto === false) !== (sp.auto === false) ||
        !m.packs.includes(s.sceneId)
      )
        errors.push(
          `${SCENE_ID} scene.json: spot ${name} not as in ${s.sceneId}`,
        );
    }
    for (const x of s.exits)
      if (!merged.exits.some((y) => y.place === x.place && y.spot === x.spot))
        errors.push(`${SCENE_ID} scene.json: exit to ${x.place} missing`);
    if (
      !isDeepStrictEqual(
        merged.startSpotsByAct[layout.select.act],
        s.startSpots,
      )
    )
      errors.push(
        `${SCENE_ID} scene.json: startSpotsByAct ${layout.select.act} is not ${s.sceneId}'s`,
      );
  }
  for (const [name, m] of Object.entries(merged.spots))
    for (const p of m.packs)
      if (!packs.find((x) => x.scene.sceneId === p)?.scene.spots[name])
        errors.push(`${SCENE_ID} scene.json: spot ${name} says it is in ${p}`);
  if (new Set(index.packs.map((p) => p.act)).size !== index.packs.length)
    errors.push(`${SCENE_ID} index.json: two packs for the same act`);
  // every act of a world model that has this scene picks exactly one pack (the page goes by act)
  let usedBy = 0;
  for (const { f, w } of worlds) {
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
  if (!usedBy)
    errors.push(`no world model in worlds/ has ${SCENE_ID} in an act`);
}

console.log(rows.join("\n"));
if (errors.length) {
  console.error(`\n${errors.length} problem(s):\n- ${errors.join("\n- ")}`);
  process.exit(1);
}
console.log("ok");
