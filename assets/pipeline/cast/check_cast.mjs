// The characters' budgets (F-16; budgets.json "character", frontend-design 10.6.2) and the committed manifest.
//   node check_cast.mjs <build_dir> <manifest.json> [--require-all]
// build_dir/<name>/ holds what build.sh wrote: the four glbs and compress.mjs's report. The manifest (in git, the files
// are not) lists each character's files with their size, sha256 and triangles; build.sh refreshes it. Exits 1 on a
// file over its budget.
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [, , BUILD, MANIFEST] = process.argv;
const requireAll = process.argv.includes("--require-all");
const here = path.dirname(fileURLToPath(import.meta.url));
const budgets = JSON.parse(
  fs.readFileSync(path.join(here, "../../budgets.json"), "utf8"),
).character;
const spec = JSON.parse(
  fs.readFileSync(path.join(here, "characters.json"), "utf8"),
).characters;
const MB = 1024 * 1024;

const TIERS = {
  "talk_high.glb": ["talkHigh", (b, r) => r.tris <= b.maxTris],
  "talk_std.glb": [
    "talkStd",
    (b, r) => r.tris >= b.tris[0] && r.tris <= b.tris[1],
  ],
  "walk.glb": [
    "walk",
    (b, r) =>
      r.tris <= b.maxTris &&
      r.materials <= b.materials &&
      r.joints <= b.maxBones,
  ],
  "anims.glb": ["anims", () => true],
};

// name -> { id, variant }
const names = {};
for (const [k, v] of Object.entries(spec)) {
  names[k] = { id: v.id, variant: null };
  for (const n of Object.keys(v.variants ?? {}))
    names[n] = { id: v.id, variant: n };
}

const manifest = {
  version: 1,
  source: "assets/pipeline/cast/build.sh (F-16)",
  characters: {},
};
const errors = [];
for (const name of Object.keys(names).sort()) {
  const dir = path.join(BUILD, name);
  if (!fs.existsSync(path.join(dir, "compress_report.json"))) {
    if (requireAll) errors.push(`${name}: missing compress_report.json`);
    continue;
  }
  const reports = JSON.parse(
    fs.readFileSync(path.join(dir, "compress_report.json"), "utf8"),
  );
  const files = {};
  for (const [file, [tier, ok]] of Object.entries(TIERS)) {
    const p = path.join(dir, file);
    if (!fs.existsSync(p)) {
      errors.push(`${name}/${file}: missing`);
      continue;
    }
    const buf = fs.readFileSync(p);
    const gltf = JSON.parse(
      buf.subarray(20, 20 + buf.readUInt32LE(12)).toString("utf8"),
    );
    const nonNeutral = [...(gltf.meshes ?? []), ...(gltf.nodes ?? [])].some(
      (item) => item.weights?.some((weight) => weight !== 0),
    );
    if (nonNeutral)
      errors.push(`${name}/${file}: non-neutral default morph weights`);
    const r = reports.find((x) => x.file === file) ?? {};
    const b = budgets[tier];
    const entry = {
      bytes: buf.length,
      sha256: crypto.createHash("sha256").update(buf).digest("hex"),
      tris: r.tris ?? 0,
      ...(r.morphs ? { morphs: r.morphs } : {}),
      ...(r.anims?.length ? { clips: r.anims } : {}),
    };
    files[file.replace(".glb", "")] = entry;
    if (tier === "anims" && buf.length > budgets.sharedAnimsMb * MB)
      errors.push(
        `${name}/${file}: ${(buf.length / MB).toFixed(2)} MB > ${budgets.sharedAnimsMb} MB`,
      );
    if (b?.maxMb && buf.length > b.maxMb * MB)
      errors.push(
        `${name}/${file}: ${(buf.length / MB).toFixed(2)} MB > ${b.maxMb} MB`,
      );
    if (b && !ok(b, r))
      errors.push(
        `${name}/${file}: ${JSON.stringify({ tris: r.tris, materials: r.materials, joints: r.joints })} over ${tier}`,
      );
  }
  manifest.characters[name] = { ...names[name], files };
}
if (!Object.keys(manifest.characters).length)
  errors.push(`nothing built in ${BUILD}`);
// keep what an earlier run built for characters this run left out
if (fs.existsSync(MANIFEST)) {
  const old = JSON.parse(fs.readFileSync(MANIFEST, "utf8"));
  for (const [k, v] of Object.entries(old.characters ?? {}))
    manifest.characters[k] ??= v;
}
manifest.characters = Object.fromEntries(
  Object.entries(manifest.characters).sort(([a], [b]) => a.localeCompare(b)),
);
for (const [k, v] of Object.entries(manifest.characters))
  console.log(
    k,
    Object.entries(v.files)
      .map(([f, e]) => `${f} ${(e.bytes / MB).toFixed(2)} MB ${e.tris}`)
      .join(", "),
  );
if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}
fs.writeFileSync(MANIFEST, JSON.stringify(manifest, null, 2) + "\n");
