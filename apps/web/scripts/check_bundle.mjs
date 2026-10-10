// Bundle budgets (frontend-design 10.1, assets/budgets.json "web"; brotli q11 like the measurements in 15):
// the shell (entry chunk and what it imports statically) <= firstScreenJsKbBrotli, the 3D chunk (the world screen's
// dynamic chunk and its own static imports) <= threeChunkKb. Run after `pnpm build`; exits 1 over budget.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";

const here = path.dirname(fileURLToPath(import.meta.url));
const dist = path.join(here, "../dist");
const budgets = JSON.parse(
  fs.readFileSync(path.join(here, "../../../assets/budgets.json"), "utf8"),
).web;
const manifest = JSON.parse(
  fs.readFileSync(path.join(dist, ".vite/manifest.json"), "utf8"),
);

const br = (file) =>
  zlib.brotliCompressSync(fs.readFileSync(path.join(dist, file)), {
    params: { [zlib.constants.BROTLI_PARAM_QUALITY]: 11 },
  }).length / 1024;

// a chunk and its static imports, minus chunks already counted elsewhere
function closure(key, skip = new Set()) {
  const out = new Set();
  const walk = (k) => {
    if (out.has(k) || skip.has(k)) return;
    out.add(k);
    for (const i of manifest[k].imports ?? []) walk(i);
  };
  walk(key);
  return out;
}

const entry = Object.keys(manifest).find((k) => manifest[k].isEntry);
const world = Object.keys(manifest).find(
  (k) => manifest[k].isDynamicEntry && k.endsWith("WorldScreen.tsx"),
);
if (!entry || !world)
  throw new Error(
    "dist/.vite/manifest.json has no entry or no WorldScreen chunk: run pnpm build",
  );
const shell = closure(entry);
const three = closure(world, shell);
const sum = (keys) => [...keys].reduce((n, k) => n + br(manifest[k].file), 0);

const rows = [
  ["shell (first screen JS)", sum(shell), budgets.firstScreenJsKbBrotli],
  ["3D chunk", sum(three), budgets.threeChunkKb],
];
let over = false;
for (const [name, kb, max] of rows) {
  const ok = kb <= max;
  over ||= !ok;
  console.log(
    `${ok ? "ok  " : "OVER"} ${name}: ${kb.toFixed(1)} KB brotli (budget ${max})`,
  );
}
// loaded by KTX2Loader's worker when the textures arrive; not part of either chunk, listed so it stays in view
for (const [k, v] of Object.entries(manifest))
  if (k.includes("basis_transcoder"))
    console.log(
      `     ${path.basename(v.file)}: ${br(v.file).toFixed(1)} KB brotli`,
    );
process.exit(over ? 1 : 0);
