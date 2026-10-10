// Decode a KTX2 file in Node with the same Basis transcoder the page uses (three/examples/jsm/libs/basis), so the
// two-tier colour check (ux/art-direction 9.5) looks at what the phone will show, not at the PNG before encoding.
import fs from "fs";
import { createRequire } from "module";

const require = createRequire(import.meta.url);
const DIR = new URL(
  "../node_modules/three/examples/jsm/libs/basis/",
  import.meta.url,
).pathname;
let basis = null;

async function transcoder() {
  if (basis) return basis;
  // an Emscripten CommonJS build inside an ES-module package: load it by hand
  const mod = { exports: {} };
  const code = fs.readFileSync(DIR + "basis_transcoder.js", "utf8");
  new Function("module", "exports", "require", "__filename", "__dirname", code)(
    mod,
    mod.exports,
    require,
    DIR + "basis_transcoder.js",
    DIR,
  );
  basis = await mod.exports({
    wasmBinary: fs.readFileSync(DIR + "basis_transcoder.wasm"),
  });
  basis.initializeBasis();
  return basis;
}

// -> { width, height, rgba: Uint8Array } of mip level 0
export async function decodeKTX2(buf) {
  const M = await transcoder();
  const f = new M.KTX2File(new Uint8Array(buf));
  try {
    if (!f.isValid() || !f.startTranscoding())
      throw new Error("not a valid KTX2 file");
    const RGBA32 = 13; // basisu cTFRGBA32
    const rgba = new Uint8Array(
      f.getImageTranscodedSizeInBytes(0, 0, 0, RGBA32),
    );
    if (!f.transcodeImage(rgba, 0, 0, 0, RGBA32, 0, -1, -1))
      throw new Error("transcode failed");
    return { width: f.getWidth(), height: f.getHeight(), rgba };
  } finally {
    f.close();
    f.delete();
  }
}

export function meanRGB(rgba) {
  const s = [0, 0, 0];
  for (let i = 0; i < rgba.length; i += 4)
    for (let c = 0; c < 3; c++) s[c] += rgba[i + c];
  return s.map((v) => +(v / (rgba.length / 4)).toFixed(2));
}
