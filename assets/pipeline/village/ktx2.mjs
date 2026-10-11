// KTX2 for the sub-packs (F-11): the same encoder settings as ../plaza/pack_scene.mjs (which runs its whole pack on
// import, so its copy stays there and its inputs do not change). kind: 'color' (ETC1S, sRGB), 'linear' (ETC1S),
// 'normal' (UASTC + zstd). mean = the decoded result's average colour.
import { encodeToKTX2 } from "ktx2-encoder";
import sharp from "sharp";
import { decodeKTX2, meanRGB } from "../plaza/ktx2_decode.mjs";

const decoder = async (buf) => {
  const { data, info } = await sharp(buf)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });
  return { data: new Uint8Array(data), width: info.width, height: info.height };
};

export async function ktx2(src, size, kind) {
  const png = await sharp(src)
    .resize(size, size, { kernel: "lanczos3", fit: "fill" })
    .png()
    .toBuffer();
  const opts =
    kind === "normal"
      ? {
          isUASTC: true,
          needSupercompression: true,
          generateMipmap: true,
          isNormalMap: true,
          imageDecoder: decoder,
        }
      : {
          isUASTC: false,
          generateMipmap: true,
          qualityLevel: 160,
          compressionLevel: 2,
          isSetKTX2SRGBTransferFunc: kind === "color",
          imageDecoder: decoder,
        };
  const log = console.log;
  console.log = () => {}; // the Basis encoder prints every mip level
  let out;
  try {
    out = Buffer.from(await encodeToKTX2(new Uint8Array(png), opts));
  } finally {
    console.log = log;
  }
  return { buf: out, mean: meanRGB((await decodeKTX2(out)).rgba) };
}
