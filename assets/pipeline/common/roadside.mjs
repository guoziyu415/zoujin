// The shared roadside pack road-common (F-10, F-11 card 2): one fixed table of texture keys every stop of the road and
// the village take from it, and the step that moves a pack's copies of them there. The road's merge_river.mjs and the
// village's build.sh both call it; the table is only here.
// - road-common/pack.json: the shared textures (their std and hi KTX2 files), not a scene, so not named scene.json
//   (the backend reads every assets/scenes/*/scene.json as a scene layout). A build adds what its packs use to what
//   the directory already holds; a key it brings again with other bytes replaces the old entry (the other packs'
//   checks then fail until they are rebuilt).
// - each pack's scene.json: those files stay in its file list with `shared: "road-common"` (the path is relative to
//   the shared pack); bytes.entry / hiExtra count the pack's own files, bytes.shared only the shared files this pack
//   uses (not all of road-common: a key added for another stop does not count against this one's first visit), and
//   envStd / envHi are the first visit with nothing cached (own + shared).
import crypto from "crypto";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

export const SHARED = "road-common";
// ux/scenes/homeward-road.md 0.4 and village.md 0.4: road, dry grass, limestone (outcrops and dry-stone walls),
// gravel, bark, the white poplar and the holm oak, the far hills, and the wheat (added with the village, F-11)
export const KEYS = [
  "road",
  "grass",
  "outcrop",
  "gravel",
  "bark",
  "poplar",
  "holmoak",
  "hill",
  "wheat",
];

export const stemOf = (key) => key.slice(0, key.lastIndexOf("_"));
export const sha = (b) => crypto.createHash("sha256").update(b).digest("hex");
const readJson = (f) => JSON.parse(fs.readFileSync(f, "utf8"));
const write = (f, obj) =>
  fs.writeFileSync(f, JSON.stringify(obj, null, 1) + "\n");
const sum = (files, pack) =>
  files.filter((f) => f.pack === pack).reduce((s, f) => s + f.bytes, 0);

// the bytes of a pack's own files and of the shared files it uses
export function packBytes(scene) {
  const own = scene.files.filter((f) => !f.shared);
  const shr = scene.files.filter((f) => f.shared);
  const b = {
    entry: sum(own, "entry"),
    hiExtra: sum(own, "hi"),
    shared: { entry: sum(shr, "entry"), hiExtra: sum(shr, "hi") },
  };
  b.envStd = b.entry + b.shared.entry;
  b.envHi = b.envStd + b.hiExtra + b.shared.hiExtra;
  return b;
}

// move the shared textures of the packs in packDirs (each with its scene.json, or pack.json for a sub-pack) into
// commonDir; manifestName: the packs' manifest file name
export function share(packDirs, commonDir, note, manifestName = "scene.json") {
  fs.mkdirSync(commonDir, { recursive: true });
  const cpath = path.join(commonDir, "pack.json");
  const common = fs.existsSync(cpath)
    ? readJson(cpath)
    : { textures: {}, files: [] };
  const packs = packDirs.map((dir) => ({
    dir,
    scene: readJson(path.join(dir, manifestName)),
  }));
  const errors = [];
  const brought = new Map(); // key -> the first pack bringing it this run
  for (const p of packs)
    for (const [key, t] of Object.entries(p.scene.textures)) {
      if (!KEYS.includes(stemOf(key))) continue;
      const first = brought.get(key);
      if (first) {
        const u = first.scene.textures[key];
        if (
          u.sourceSha256 !== t.sourceSha256 ||
          u.std.file !== t.std.file ||
          u.hi?.file !== t.hi?.file
        )
          errors.push(
            `${key}: ${first.scene.sceneId} and ${p.scene.sceneId} disagree (source or tiers)`,
          );
        continue;
      }
      brought.set(key, p);
    }
  for (const [key, p] of [...brought].sort(([a], [b]) => (a < b ? -1 : 1))) {
    const t = { ...p.scene.textures[key] };
    delete t.shared;
    const old = common.textures[key];
    for (const rel of [t.std.file, t.hi?.file].filter(Boolean)) {
      const f = p.scene.files.find((x) => x.path === rel);
      const src = path.join(p.dir, rel);
      const dst = path.join(commonDir, rel);
      const buf = fs.existsSync(src) ? fs.readFileSync(src) : null;
      if (!buf) {
        // already moved by an earlier run of this step on this pack
        if (!f?.shared) errors.push(`${p.scene.sceneId} ${rel}: missing`);
        continue;
      }
      for (const q of packs) {
        if (!q.scene.textures[key]) continue;
        const g = q.scene.files.find((x) => x.path === rel);
        if (!g || g.sha256 !== sha(buf))
          errors.push(`${rel}: not the same bytes in ${q.scene.sceneId}`);
      }
      const prev = common.files.find((x) => x.path === rel);
      if (prev && prev.sha256 !== f.sha256)
        console.warn(
          `${SHARED} ${rel}: replaced (other packs using it must be rebuilt)`,
        );
      fs.mkdirSync(path.dirname(dst), { recursive: true });
      fs.writeFileSync(dst, buf);
      common.files = common.files.filter((x) => x.path !== rel);
      common.files.push({
        path: rel,
        bytes: f.bytes,
        sha256: f.sha256,
        pack: f.pack,
      });
      for (const q of packs)
        if (q.scene.textures[key] && fs.existsSync(path.join(q.dir, rel)))
          fs.rmSync(path.join(q.dir, rel));
    }
    if (old && old.hi && !t.hi)
      common.files = common.files.filter((x) => x.path !== old.hi.file);
    common.textures[key] = t;
  }
  if (errors.length) throw new Error(errors.join("\n"));
  common.files.sort((a, b) => (a.path < b.path ? -1 : 1));
  common.textures = Object.fromEntries(
    Object.entries(common.textures).sort(([a], [b]) => (a < b ? -1 : 1)),
  );
  const sharedPaths = new Set(common.files.map((f) => f.path));
  const out = {
    version: 1,
    pack: SHARED,
    note: `Generated by ${note}; do not edit by hand.`,
    about:
      "Roadside textures every stop of the homeward road and the village share (ux/scenes/homeward-road.md 0.4, village.md 0.4), one fixed table of keys (assets/pipeline/common/roadside.mjs), each file downloaded once. A pack's manifest lists the files it uses with shared: road-common; paths are relative to this pack.",
    keys: KEYS,
    textures: common.textures,
    files: common.files,
    bytes: {
      entry: sum(common.files, "entry"),
      hiExtra: sum(common.files, "hi"),
    },
  };
  write(cpath, out);
  for (const p of packs) {
    const s = p.scene;
    s.sharedPacks = [SHARED];
    for (const f of s.files) if (sharedPaths.has(f.path)) f.shared = SHARED;
    for (const k of Object.keys(s.textures))
      if (KEYS.includes(stemOf(k))) s.textures[k].shared = SHARED;
    s.bytes = packBytes(s);
    write(path.join(p.dir, manifestName), s);
  }
  return { common: out, packs };
}

// node roadside.mjs <road-common dir> <generated-by note> <pack dir>...
if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const [commonDir, note, ...dirs] = process.argv.slice(2);
  share(dirs, commonDir, note);
}
