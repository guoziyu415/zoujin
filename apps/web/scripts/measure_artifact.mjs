// Packs the measuring page as a claude.ai private page to open on a phone without a deploy (F-2 card range 6):
//   pnpm --filter @zoujin/web exec vite build --base ./ --outDir <tmp>/dist
//   node apps/web/scripts/measure_artifact.mjs <tmp>/dist <tmp>/page
// then publish <tmp>/page/index.html with the other files of <tmp>/page next to it. The page host serves only common
// web types, so the scene's .glb and .ktx2 files and the Basis .wasm ride along as base64 in script files and a small
// fetch shim hands them to the loaders. Load times on that page include the base64 decoding: read the frame times
// and GPU times from it, not the first-entry time.
import fs from "node:fs";
import path from "node:path";

const [dist, out] = process.argv.slice(2);
if (!dist || !out) {
  console.error(
    "usage: measure_artifact.mjs <dist built with --base ./> <out dir>",
  );
  process.exit(2);
}
const BINARY = new Set([".glb", ".ktx2", ".wasm"]);
const MAX_SCRIPT = 12 * 2 ** 20; // under the host's 16 MB per file, with room

fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(path.join(out, "blobs"), { recursive: true });

const walk = (dir) =>
  fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    return e.isDirectory() ? walk(p) : [p];
  });

const blobScripts = [];
let chunk = [];
let chunkBytes = 0;
const flush = () => {
  if (!chunk.length) return;
  const name = `blobs/b${blobScripts.length}.js`;
  fs.writeFileSync(
    path.join(out, name),
    chunk.map(([k, b64]) => `__zb[${JSON.stringify(k)}]="${b64}";`).join("\n"),
  );
  blobScripts.push(name);
  chunk = [];
  chunkBytes = 0;
};
for (const file of walk(dist)) {
  const rel = path.relative(dist, file).split(path.sep).join("/");
  if (rel.startsWith(".vite/") || rel.endsWith(".md")) continue;
  if (rel === "index.html") continue;
  if (BINARY.has(path.extname(file))) {
    const b64 = fs.readFileSync(file).toString("base64");
    if (chunkBytes + b64.length > MAX_SCRIPT) flush();
    chunk.push([rel, b64]);
    chunkBytes += b64.length;
  } else {
    fs.mkdirSync(path.dirname(path.join(out, rel)), { recursive: true });
    fs.copyFileSync(file, path.join(out, rel));
  }
}
flush();

const shim = `window.__ZOUJIN_MEASURE = true;
window.__zb = {};
(function () {
  var types = { ".glb": "model/gltf-binary", ".ktx2": "image/ktx2", ".wasm": "application/wasm" };
  var orig = window.fetch.bind(window);
  window.fetch = function (input, init) {
    var url = new URL(typeof input === "string" || input instanceof URL ? String(input) : input.url, document.baseURI);
    var base = new URL(".", document.baseURI).href;
    var key = url.href.indexOf(base) === 0 ? url.href.slice(base.length).split("?")[0] : null;
    var b64 = key && window.__zb[key];
    if (!b64) return orig(input, init);
    var s = atob(b64), bin = new Uint8Array(s.length);
    for (var i = 0; i < s.length; i++) bin[i] = s.charCodeAt(i);
    var ext = key.slice(key.lastIndexOf("."));
    return Promise.resolve(new Response(bin, { status: 200, headers: { "Content-Type": types[ext] || "application/octet-stream" } }));
  };
})();
`;
fs.writeFileSync(path.join(out, "blobs/shim.js"), shim);

let html = fs.readFileSync(path.join(dist, "index.html"), "utf8");
const tags = ["blobs/shim.js", ...blobScripts]
  .map((s) => `<script src="${s}"></script>`)
  .join("\n");
html = html
  .replace(/<title>[^<]*<\/title>/, "<title>画质计测</title>")
  .replace(/<script type="module"/, `${tags}\n<script type="module"`);
fs.writeFileSync(path.join(out, "index.html"), html);
const total = walk(out).reduce((n, f) => n + fs.statSync(f).size, 0);
console.log(
  `${walk(out).length} files, ${(total / 2 ** 20).toFixed(1)} MB in ${out}`,
);
