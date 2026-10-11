// After pack_scene.mjs, before merge_river.mjs (F-10, UX round 2): the foliage textures (leaf clusters, willow
// strands, reeds; road_tex.py draws them at 512 and 256 with alpha) are encoded again at their own size. The plaza's
// pack step blows every colour texture up to 1024, which would make each of them three times the bytes for nothing;
// changing that step would change the plaza's recorded inputs. Rewrites the pack's tex/std file, its size and mean in
// scene.json and its bytes and sha256 in the file list.
// node small_tex.mjs <work_dir> <pack_dir>
import crypto from "crypto";
import fs from "fs";
import path from "path";
import sharp from "sharp";
import { encodeToKTX2 } from "ktx2-encoder";
import { decodeKTX2, meanRGB } from "../plaza/ktx2_decode.mjs";

const [WORK, PACK] = process.argv.slice(2);
const scene = JSON.parse(
  fs.readFileSync(path.join(PACK, "scene.json"), "utf8"),
);
const sha = (b) => crypto.createHash("sha256").update(b).digest("hex");
// the same encoder settings as pack_scene.mjs's colour textures
const decoder = async (buf) => {
  const { data, info } = await sharp(buf)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });
  return { data: new Uint8Array(data), width: info.width, height: info.height };
};

for (const [key, t] of Object.entries(scene.textures)) {
  if (t.slot !== "base") continue;
  const src = fs.readFileSync(path.join(WORK, "tex", `${key}.png`));
  const { width } = await sharp(src).metadata();
  if (!width || width >= t.std.size) continue;
  const log = console.log;
  console.log = () => {}; // the Basis encoder prints every mip level
  let buf;
  try {
    buf = Buffer.from(
      await encodeToKTX2(new Uint8Array(src), {
        isUASTC: false,
        generateMipmap: true,
        qualityLevel: 160,
        compressionLevel: 2,
        isSetKTX2SRGBTransferFunc: true,
        imageDecoder: decoder,
      }),
    );
  } finally {
    console.log = log;
  }
  fs.writeFileSync(path.join(PACK, t.std.file), buf);
  t.std.size = width;
  t.std.mean = meanRGB((await decodeKTX2(buf)).rgba);
  const f = scene.files.find((x) => x.path === t.std.file);
  f.bytes = buf.length;
  f.sha256 = sha(buf);
  console.log("small", key, width, buf.length);
}
fs.writeFileSync(
  path.join(PACK, "scene.json"),
  JSON.stringify(scene, null, 1) + "\n",
);
