// CI gate for a packed scene (F-2): download budgets (frontend-design 10.6.2), texture memory, the two tiers keeping
// the same colour (ux/art-direction 9.5), and scene.json agreeing with layout.json.
// node check_scene.mjs <dir with scene.json> [layout.json]
// When the packed files sit next to scene.json (a fresh build) their sizes and sha256 are checked and the colour
// textures are decoded again; with scene.json alone (the committed manifest) the recorded numbers are checked.
import crypto from "crypto";
import fs from "fs";
import path from "path";
import { decodeKTX2, meanRGB } from "./ktx2_decode.mjs";
import { planToWorld, pointInPolygon } from "./frame.mjs";

const [, , DIR, LAYOUT_ARG] = process.argv;
const HERE = path.dirname(new URL(import.meta.url).pathname);
const budgets = JSON.parse(
  fs.readFileSync(path.join(HERE, "../../budgets.json"), "utf8"),
).scene;
const scene = JSON.parse(fs.readFileSync(path.join(DIR, "scene.json"), "utf8"));
const layoutPath =
  LAYOUT_ARG ??
  [path.join(DIR, "layout.json"), path.join(DIR, "../layout.json")].find((p) =>
    fs.existsSync(p),
  );
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
const present = scene.files.every((f) => fs.existsSync(path.join(DIR, f.path)));
if (present) {
  for (const f of scene.files) {
    const buf = fs.readFileSync(path.join(DIR, f.path));
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
  scene.files.filter(pred).reduce((s, f) => s + f.bytes, 0);
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
    a = meanRGB(
      (await decodeKTX2(fs.readFileSync(path.join(DIR, t.std.file)))).rgba,
    );
    b = meanRGB(
      (await decodeKTX2(fs.readFileSync(path.join(DIR, t.hi.file)))).rgba,
    );
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
