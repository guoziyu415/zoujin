// The castle's lamp light (F-14), after ../plaza/pack_scene.mjs: that packs the indirect lightmap and the occlusion
// (the plaza's day is the live sun); here the bake is the lamps' night, and the page needs the whole of it. Adds
//   lm/<mesh>_full.ktx2   the full bake (the lamps' direct light and its bounce, the starlit sky), K as encode.py
// to the pack and scene.json (lightmaps.<mesh>.full, the files list, the byte counts), and copies the layout's lamps
// and the hall box into scene.json in glTF coordinates (the page draws the flames and keeps the hall lamp-lit).
// The plaza's scripts stay as they are, so the plaza's and the river's manifests keep their inputs.
// node lamps.mjs <work_dir> <layout.json> <out_dir>
import { encodeToKTX2 } from "ktx2-encoder";
import sharp from "sharp";
import crypto from "crypto";
import fs from "fs";
import path from "path";
import { planToWorld } from "../plaza/frame.mjs";

const [, , WORK, LAYOUT, OUT] = process.argv;
const layout = JSON.parse(fs.readFileSync(LAYOUT, "utf8"));
const scenePath = path.join(OUT, "scene.json");
const scene = JSON.parse(fs.readFileSync(scenePath, "utf8"));
const meta = JSON.parse(
  fs.readFileSync(path.join(WORK, "lm_meta.json"), "utf8"),
);
const ROT = layout.rotationDeg;
const sha = (buf) => crypto.createHash("sha256").update(buf).digest("hex");

const decoder = async (buf) => {
  const { data, info } = await sharp(buf)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });
  return { data: new Uint8Array(data), width: info.width, height: info.height };
};

// the same settings as pack_scene.mjs's colour lightmaps (ETC1S, sRGB, mipmaps)
async function ktx2(src, size) {
  const png = await sharp(src)
    .resize(size, size, { kernel: "lanczos3", fit: "fill" })
    .png()
    .toBuffer();
  const log = console.log;
  console.log = () => {};
  try {
    return Buffer.from(
      await encodeToKTX2(new Uint8Array(png), {
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
}

for (const mesh of ["ground", "arch"]) {
  const buf = await ktx2(
    fs.readFileSync(path.join(WORK, `lm_${mesh}_full.png`)),
    scene.lightmaps.res,
  );
  const rel = `lm/${mesh}_full.ktx2`;
  fs.writeFileSync(path.join(OUT, rel), buf);
  scene.files.push({
    path: rel,
    bytes: buf.length,
    sha256: sha(buf),
    pack: "entry",
  });
  // three.js: lightMapIntensity = PI * K (encode.py stores baked / K, sRGB-encoded)
  scene.lightmaps[mesh].full = { file: rel, K: meta[mesh].K_full };
}

const w = (x, y, z) =>
  planToWorld(x, y, z, ROT).map((v) => Math.round(v * 1000) / 1000);
scene.lamps = layout.lamps.map((l) => {
  const centre = w(l.at[0], l.at[1], l.z);
  const flames =
    l.kind === "chandelier"
      ? Array.from({ length: l.cups }, (_, k) => {
          const a = (2 * Math.PI * (k + 0.5)) / l.cups;
          return w(
            l.at[0] + l.radius * Math.cos(a),
            l.at[1] + l.radius * Math.sin(a),
            l.z + 0.1,
          );
        })
      : [w(l.at[0], l.at[1], l.z - 0.02)];
  return { id: l.id, kind: l.kind, indoor: l.indoor, pos: centre, flames };
});
// the hall box in glTF: plan y -> -z
const [ax, , az] = w(layout.hall.x[0], layout.hall.y[1], 0);
const [bx, , bz] = w(layout.hall.x[1], layout.hall.y[0], 0);
scene.hall = {
  min: [Math.min(ax, bx), layout.hall.z[0], Math.min(az, bz)],
  max: [Math.max(ax, bx), layout.hall.z[1], Math.max(az, bz)],
};

const sum = (pred) => scene.files.filter(pred).reduce((s, f) => s + f.bytes, 0);
scene.bytes.entry = sum((f) => f.pack === "entry");
scene.bytes.hiExtra = sum((f) => f.pack === "hi");
scene.bytes.envStd = scene.bytes.entry;
scene.bytes.envHi = scene.bytes.entry + scene.bytes.hiExtra;
fs.writeFileSync(scenePath, JSON.stringify(scene, null, 1) + "\n");
console.log(
  `lamps: ${scene.lamps.length} lamps, full lightmaps added, entry ${(scene.bytes.entry / 1e6).toFixed(2)} MB`,
);
