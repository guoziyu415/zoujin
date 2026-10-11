// CI gate for the crowd pack (F-4): the budgets (assets/budgets.json "crowd"), and a pack the runtime
// (apps/web/src/three/crowd/pack.ts) can read: every offset inside crowd.bin, the weights of a vertex adding to 255,
// bone and vertex indices in range, the parts 0-3.
// node check_crowd.mjs <dir with crowd.json> [--manifest <committed crowd.json>]
// With crowd.bin next to crowd.json (a fresh build) its size and sha256 are checked and every vertex is read; with
// crowd.json alone (the committed manifest) the recorded numbers are checked, and the script it was built from must
// still be the one in the repo. --manifest: the committed manifest must be this fresh build's, byte for byte.
import crypto from "crypto";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const args = process.argv.slice(2);
const at = args.indexOf("--manifest");
const MANIFEST = at < 0 ? undefined : args.splice(at, 2)[1];
const [DIR] = args;
const HERE = path.dirname(fileURLToPath(import.meta.url));
const budget = JSON.parse(
  fs.readFileSync(path.join(HERE, "../../budgets.json"), "utf8"),
).crowd;
const text = fs.readFileSync(path.join(DIR, "crowd.json"), "utf8");
const pack = JSON.parse(text);
const errors = [];
const fail = (m) => errors.push(m);

if (pack.format !== "zoujin-crowd-1") fail(`format ${pack.format}`);
const bones = pack.bones ?? [];
if (bones.length > budget.maxBones)
  fail(`${bones.length} bones > ${budget.maxBones}`);
bones.forEach((b, i) => {
  if (!(b.parent < i)) fail(`bone ${b.name}: parent ${b.parent} not before it`);
});
if (pack.bytes > budget.packKb * 1024)
  fail(`pack ${pack.bytes} B > ${budget.packKb} KB`);
const costumes = Object.entries(pack.costumes ?? {});
if (costumes.length !== 3) fail(`${costumes.length} costumes, not 3`);
for (const [name, c] of costumes) {
  if (c.triangles > budget.maxTrisPerBody)
    fail(`${name}: ${c.triangles} triangles > ${budget.maxTrisPerBody}`);
  if (c.indices !== c.triangles * 3) fail(`${name}: indices ≠ 3 × triangles`);
  if (c.joints?.length !== bones.length)
    fail(`${name}: ${c.joints?.length} joints for ${bones.length} bones`);
  if (c.vertices > 65535) fail(`${name}: too many vertices for u16 indices`);
}

const bin = path.join(DIR, "crowd.bin");
if (fs.existsSync(bin)) {
  const buf = fs.readFileSync(bin);
  if (buf.length !== pack.bytes)
    fail(`crowd.bin is ${buf.length} B, manifest says ${pack.bytes}`);
  const sha = crypto.createHash("sha256").update(buf).digest("hex");
  if (sha !== pack.sha256) fail(`crowd.bin sha256 ${sha} ≠ manifest`);
  for (const [name, c] of costumes) {
    const n = c.vertices;
    // position 12, normal 8, skinIndex 4, skinWeight 4, part 1 bytes a vertex, then padding to 4
    const end = c.offset + n * 29;
    if (c.offset % 4 || c.indexOffset < end || c.indexOffset % 4)
      fail(`${name}: offsets ${c.offset} / ${c.indexOffset}`);
    if (c.indexOffset + c.indices * 2 > buf.length) {
      fail(`${name}: indices run past the end`);
      continue;
    }
    const idx = c.offset + n * 20;
    const wts = idx + n * 4;
    const parts = wts + n * 4;
    for (let v = 0; v < n; v++) {
      let sum = 0;
      for (let k = 0; k < 4; k++) {
        sum += buf[wts + v * 4 + k];
        if (buf[wts + v * 4 + k] && buf[idx + v * 4 + k] >= bones.length)
          fail(`${name}: vertex ${v} bone ${buf[idx + v * 4 + k]}`);
      }
      if (sum !== 255) fail(`${name}: vertex ${v} weights add to ${sum}`);
      if (buf[parts + v] > 3)
        fail(`${name}: vertex ${v} part ${buf[parts + v]}`);
      if (errors.length > 20) break;
    }
    for (let i = 0; i < c.indices; i++)
      if (buf.readUInt16LE(c.indexOffset + i * 2) >= n) {
        fail(`${name}: index ${i} out of range`);
        break;
      }
  }
} else {
  // the committed manifest alone: still the script in the repo?
  const script = "assets/pipeline/crowd/build_crowd.py";
  const sha = crypto
    .createHash("sha256")
    .update(fs.readFileSync(path.join(HERE, "build_crowd.py")))
    .digest("hex");
  if (pack.inputs?.[script] !== sha)
    fail(`${script} changed since this manifest was built: run build.sh`);
}

if (MANIFEST && fs.readFileSync(MANIFEST, "utf8") !== text)
  fail(`${MANIFEST} is not this build's manifest: run build.sh and commit it`);

for (const [name, c] of costumes)
  console.log(`${name}: ${c.vertices} vertices, ${c.triangles} triangles`);
console.log(
  `${bones.length} bones, ${(pack.bytes / 1024).toFixed(1)} KB (budget ${budget.packKb} KB)`,
);
if (errors.length) {
  for (const e of errors) console.error(`✗ ${e}`);
  process.exit(1);
}
console.log("crowd pack ok");
