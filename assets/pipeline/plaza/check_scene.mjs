// CI gate for a packed scene (F-2): download budgets (frontend-design 10.6.2), texture memory, the two tiers keeping
// the same colour (ux/art-direction 9.5), scene.json agreeing with layout.json, and both agreeing with the world
// models that use the scene (worlds/*/*/world.json: places, sceneRef, exits to adjacent places).
// node check_scene.mjs <dir with scene.json> [layout.json] [--manifest <committed scene.json>]
// When the packed files sit next to scene.json (a fresh build) their sizes and sha256 are checked and the colour
// textures are decoded again; with scene.json alone (the committed manifest) the recorded numbers are checked, and
// the layout and scripts it was built from must still be the ones in the repo (a quick staleness check).
// --manifest: the committed manifest must have been built from the same inputs as this fresh build (otherwise the
// pipeline or layout changed without a new final build).
import crypto from "crypto";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { isDeepStrictEqual } from "util";
import { decodeKTX2, meanRGB } from "./ktx2_decode.mjs";
import { planToWorld, pointInPolygon } from "./frame.mjs";

const args = process.argv.slice(2);
const opt = (name) => {
  const i = args.indexOf(name);
  return i < 0 ? undefined : args.splice(i, 2)[1];
};
const MANIFEST = opt("--manifest");
const [DIR, LAYOUT_ARG] = args;
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../../..");
const scene = JSON.parse(fs.readFileSync(path.join(DIR, "scene.json"), "utf8"));
// budgets.json: `scene` for the plaza; a pack with its own entry under `scenes` (the road, F-10) uses that on top
const allBudgets = JSON.parse(
  fs.readFileSync(path.join(HERE, "../../budgets.json"), "utf8"),
);
const budgets = {
  ...allBudgets.scene,
  ...(allBudgets.scenes?.[scene.sceneId] ?? {}),
};
// files a shared pack holds (shared: road-common) sit in that pack's directory: the same place as this pack's
// directory with the pack name swapped (assets/scenes/<pack>/build, or <out>/<pack> for a draft build)
const fileDir = (f) => {
  if (!f.shared) return DIR;
  const parts = path.resolve(DIR).split(path.sep);
  const i = parts.lastIndexOf(scene.sceneId);
  if (i < 0)
    throw new Error(
      `${DIR}: no ${scene.sceneId} in the path to find ${f.shared}`,
    );
  parts[i] = f.shared;
  return parts.join(path.sep);
};
const layoutPath =
  LAYOUT_ARG ??
  [path.join(DIR, "layout.json"), path.join(DIR, "../layout.json")].find((p) =>
    fs.existsSync(p),
  );
if (!layoutPath) {
  console.error(
    `no layout.json next to ${DIR}: pass it as the second argument`,
  );
  process.exit(1);
}
const layout = JSON.parse(fs.readFileSync(layoutPath, "utf8"));
const errors = [];
const rows = [];
const MB = 1e6;
const limit = (label, bytes, maxMb) => {
  rows.push(
    `${label.padEnd(34)} ${(bytes / MB).toFixed(2).padStart(6)} MB  (≤ ${maxMb})`,
  );
  if (bytes > maxMb * MB)
    errors.push(`${label}: ${(bytes / MB).toFixed(2)} MB > ${maxMb} MB`);
};

// ---- the files themselves, when present
const byPath = new Map(scene.files.map((f) => [f.path, f]));
const present = scene.files.every((f) =>
  fs.existsSync(path.join(fileDir(f), f.path)),
);
if (present) {
  for (const f of scene.files) {
    const buf = fs.readFileSync(path.join(fileDir(f), f.path));
    if (buf.length !== f.bytes)
      errors.push(
        `${f.path}: ${buf.length} bytes on disk, scene.json says ${f.bytes}`,
      );
    if (crypto.createHash("sha256").update(buf).digest("hex") !== f.sha256)
      errors.push(`${f.path}: sha256 differs from scene.json`);
  }
}

// ---- download budgets
const bytesOf = (pred) =>
  scene.files
    .filter((f) => !f.shared && pred(f))
    .reduce((s, f) => s + f.bytes, 0);
limit("entry pack (walkable)", scene.bytes.entry, budgets.entryPackMb);
limit(
  "  geometry + navmesh",
  bytesOf((f) => f.path === "geo.glb" || f.path === "nav.json"),
  budgets.geoNavMb,
);
limit(
  "  environment textures (std)",
  bytesOf((f) => f.path.startsWith("tex/std/")),
  budgets.envTexturesMb,
);
rows.push(
  `${"  lightmaps".padEnd(34)} ${(bytesOf((f) => f.path.startsWith("lm/")) / MB).toFixed(2).padStart(6)} MB`,
);
limit("environment total, standard", scene.bytes.envStd, budgets.envTotalMb);
limit("environment total, high", scene.bytes.envHi, budgets.envTotalHighMb);
if (scene.bytes.shared)
  rows.push(
    `${`  of which shared (${scene.sharedPacks.join(", ")})`.padEnd(34)} ${(scene.bytes.shared.entry / MB).toFixed(2).padStart(6)} MB`,
  );

// ---- texture memory (ASTC 4x4 / ETC2 RGBA ≈ 1 byte per texel, mipmaps +1/3)
const vram = (tier) => {
  let texels = 0;
  for (const t of Object.values(scene.textures)) {
    const s = (tier === "hi" && t.hi ? t.hi : t.std).size;
    texels += s * s;
  }
  texels += 4 * scene.lightmaps.res * scene.lightmaps.res;
  return (texels * 4) / 3;
};
limit("texture memory, standard (est.)", vram("std"), budgets.textureVramMb);
limit("texture memory, high (est.)", vram("hi"), budgets.textureVramMb);

// ---- two tiers, same colour
let compared = 0;
for (const [key, t] of Object.entries(scene.textures)) {
  if (!t.hi || t.slot !== "base") continue;
  let [a, b] = [t.std.mean, t.hi.mean];
  if (present) {
    const at = (rel) =>
      path.join(fileDir(byPath.get(rel) ?? { shared: t.shared }), rel);
    a = meanRGB((await decodeKTX2(fs.readFileSync(at(t.std.file)))).rgba);
    b = meanRGB((await decodeKTX2(fs.readFileSync(at(t.hi.file)))).rgba);
    if (a.some((v, i) => Math.abs(v - t.std.mean[i]) > 0.5))
      errors.push(
        `${key}: decoded std colour ${a} differs from scene.json ${t.std.mean}`,
      );
  }
  const d = Math.max(...a.map((v, i) => Math.abs(v - b[i])));
  compared++;
  if (d > budgets.tierMeanColourMaxDiff)
    errors.push(
      `${key}: std and hi average colours differ by ${d.toFixed(1)} (> ${budgets.tierMeanColourMaxDiff})`,
    );
}
rows.push(
  `two-tier colour: ${compared} textures compared${present ? " (decoded)" : ""}`,
);

// ---- scene.json agrees with layout.json
if (scene.sceneId !== layout.sceneId)
  errors.push(`sceneId ${scene.sceneId} vs layout ${layout.sceneId}`);
const placeIds = new Set([
  layout.defaultPlace,
  ...layout.places.map((p) => p.id),
]);
for (const [name, s] of Object.entries(layout.spots)) {
  const got = scene.spots[name];
  if (!got) {
    errors.push(
      `spot ${name} is in layout.json but not in scene.json (rebuild)`,
    );
    continue;
  }
  const want =
    layout.places.find((p) => pointInPolygon(s.at[0], s.at[1], p.polygon))
      ?.id ?? layout.defaultPlace;
  if (got.place !== want)
    errors.push(
      `spot ${name}: scene.json place ${got.place}, layout says ${want}`,
    );
  if ((s.auto === false) !== (got.auto === false))
    errors.push(`spot ${name}: auto differs from layout.json (rebuild)`);
  const [x, , z] = planToWorld(s.at[0], s.at[1], 0, layout.rotationDeg);
  if (Math.hypot(got.pos[0] - x, got.pos[2] - z) > 0.7)
    errors.push(
      `spot ${name} moved more than 0.7 m from layout.json (rebuild)`,
    );
}
for (const name of Object.keys(scene.spots))
  if (!layout.spots[name])
    errors.push(`spot ${name} is in scene.json only (rebuild)`);
for (const e of layout.exits) {
  if (!scene.spots[e.spot])
    errors.push(`exit to ${e.place}: spot ${e.spot} missing`);
  if (!scene.exits.some((x) => x.place === e.place && x.spot === e.spot))
    errors.push(`exit to ${e.place} missing in scene.json`);
}
for (const p of scene.places)
  if (!placeIds.has(p.id)) errors.push(`place ${p.id} is not in layout.json`);
if (!scene.spots[layout.playerStartSpot])
  errors.push(`player start spot ${layout.playerStartSpot} missing`);
if (layout.startSpots?.[layout.defaultPlace] !== layout.playerStartSpot)
  errors.push(
    `playerStartSpot ${layout.playerStartSpot} is not startSpots of the default place ${layout.defaultPlace}`,
  );
if (!isDeepStrictEqual(scene.startSpots, layout.startSpots))
  errors.push("startSpots differ from layout.json (rebuild)");
for (const id of placeIds) {
  const s = scene.startSpots?.[id];
  if (!s || scene.spots[s]?.place !== id)
    errors.push(`place ${id}: start spot ${s} missing or not in that place`);
}

// ---- the world models that use this scene: worlds/<book>/<version>/world.json
// A pack that is one state of a bigger scene (partOf, the road's river: calm or flooded, F-10) carries that scene's
// places and exits, so it is checked as that scene.
const SCENE_ID = scene.partOf ?? scene.sceneId;
const subdirs = (d) =>
  fs.existsSync(d)
    ? fs
        .readdirSync(d, { withFileTypes: true })
        .filter((e) => e.isDirectory())
        .map((e) => path.join(d, e.name))
    : [];
const worlds = subdirs(path.join(REPO, "worlds"))
  .flatMap(subdirs)
  .map((v) => path.join(v, "world.json"))
  .filter((f) => fs.existsSync(f));
let usedBy = 0;
for (const f of worlds) {
  const w = JSON.parse(fs.readFileSync(f, "utf8"));
  if (!w.scenes?.some((sc) => sc.id === SCENE_ID)) continue;
  usedBy++;
  const where = path.relative(REPO, f);
  const byId = new Map(w.places.map((p) => [p.id, p]));
  const mine = w.places.filter((p) => p.sceneRef === SCENE_ID).map((p) => p.id);
  for (const id of mine)
    if (!placeIds.has(id))
      errors.push(`${where}: ${id} is in this scene, layout.json lacks it`);
  for (const id of placeIds)
    if (!mine.includes(id))
      errors.push(`${where}: layout place ${id} is not in this scene there`);
  for (const e of layout.exits) {
    const to = byId.get(e.place);
    if (!to) {
      errors.push(`${where}: exit to unknown place ${e.place}`);
      continue;
    }
    if (to.sceneRef === SCENE_ID)
      errors.push(`${where}: exit to ${e.place}, which is in this scene`);
    // B-0 lets a player `go` from the place they stand in: adjacency counts from the place of the exit spot
    const from = scene.spots[e.spot]?.place;
    if (!from) continue;
    const adjacent =
      byId.get(from)?.adjacent?.some((a) => a.place === e.place) ||
      to.adjacent?.some((a) => a.place === from);
    if (!adjacent)
      errors.push(
        `${where}: exit to ${e.place} from ${e.spot}, but ${from} is not adjacent to it`,
      );
  }
}
rows.push(`world models using ${SCENE_ID}: ${usedBy}`);
// a scene in the repo that no world model uses means a renamed id somewhere, and the checks above checked nothing
if (usedBy === 0) errors.push(`no world model in worlds/ uses ${SCENE_ID}`);

// ---- the committed manifest alone: the layout and scripts it was built from are still the ones in the repo
if (!present)
  for (const [f, want] of Object.entries(scene.inputs?.files ?? {})) {
    const p = path.join(REPO, f);
    const got = fs.existsSync(p)
      ? crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex")
      : "missing";
    if (got !== want)
      errors.push(
        `scene.json is stale: ${f} changed since it was built (run the final build and commit scene.json)`,
      );
  }

// ---- the committed manifest was built from the same inputs as this build
if (MANIFEST) {
  const committed = JSON.parse(fs.readFileSync(MANIFEST, "utf8"));
  for (const part of ["files", "textures", "tools", "env"]) {
    const a = committed.inputs?.[part] ?? {};
    const b = scene.inputs?.[part] ?? {};
    for (const k of new Set([...Object.keys(a), ...Object.keys(b)]))
      if (a[k] !== b[k])
        errors.push(
          `${MANIFEST} is stale: ${part} ${k} differs from this build (run the final build and commit scene.json)`,
        );
  }
}
if (!byPath.has(scene.nav.file))
  errors.push("navmesh file missing from the file list");

const prims = Object.values(scene.nodes).reduce((s, n) => s + n.prims, 0);
rows.push(
  `environment: ${scene.tris} triangles, ${prims} primitives (draw calls before shadows), ${scene.nav.polys} nav polygons`,
);
rows.push(
  `quality ${scene.quality}${scene.placeholderTextures ? ", placeholder textures" : ""}${present ? "" : ", manifest only"}`,
);
console.log(rows.join("\n"));
if (errors.length) {
  console.error(`\n${errors.length} problem(s):\n- ${errors.join("\n- ")}`);
  process.exit(1);
}
console.log("ok");
