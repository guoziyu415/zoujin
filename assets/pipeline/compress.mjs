// Phone formats for the character glbs: KTX2 textures, quantized + meshopt geometry.
// node compress.mjs <in_dir> <out_dir>
// Tiers (frontend-design 10.6.2): std = all colour 1024, normals 512 (longer side) except the skin's 1024;
// high = skin colour (+normal) 2048, the rest as std; walk = one 1024 atlas.
import { NodeIO, PropertyType } from "@gltf-transform/core";
import { ALL_EXTENSIONS, KHRTextureBasisu } from "@gltf-transform/extensions";
import { prune, dedup, quantize, meshopt } from "@gltf-transform/functions";
import { MeshoptEncoder } from "meshoptimizer";
import { encodeToKTX2 } from "ktx2-encoder";
import sharp from "sharp";
import fs from "fs";
import path from "path";

const [, , IN, OUT] = process.argv;
fs.mkdirSync(OUT, { recursive: true });
const io = new NodeIO()
  .registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({ "meshopt.encoder": MeshoptEncoder });
await MeshoptEncoder.ready;

const decoder = async (buf) => {
  const { data, info } = await sharp(buf)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });
  return { data: new Uint8Array(data), width: info.width, height: info.height };
};

const ALPHA = new Set(["hair", "brows", "lashes"]);

async function encodeTexture(tex, size, isNormal) {
  const src = tex.getImage();
  // keep the aspect of non-square atlases (the teeth atlas is 2:1); size is the longer side
  const { data, info } = await sharp(Buffer.from(src))
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });
  if (isNormal) {
    // MakeHuman normal maps are black outside the UV islands; black is a wildly wrong normal and bleeds
    // into the islands in the smaller mip levels (the cloth looked faceted). Fill it with the flat normal.
    let sx = 0,
      sy = 0,
      n = 0;
    for (let i = 0; i < data.length; i += 4) {
      if (data[i] + data[i + 1] + data[i + 2] < 40) {
        data[i] = 128;
        data[i + 1] = 128;
        data[i + 2] = 255;
        continue;
      }
      sx += data[i] / 127.5 - 1;
      sy += data[i + 1] / 127.5 - 1;
      n++;
    }
    // a tangent-space map should average to straight out (0, 0, 1). The stand-in tunic's leans ~38°, which turned
    // every triangle's small tangent difference into a visible facet. Re-centre anything leaning over 10° and say so.
    const mx = sx / Math.max(1, n),
      my = sy / Math.max(1, n),
      lean = (Math.asin(Math.min(1, Math.hypot(mx, my))) * 180) / Math.PI;
    tex.setExtras({ ...tex.getExtras(), normalLeanDeg: +lean.toFixed(1) });
    if (lean > 10) {
      console.warn(
        `normal map ${tex.getName() || tex.getURI()} leans ${lean.toFixed(0)}°: re-centred`,
      );
      for (let i = 0; i < data.length; i += 4) {
        let x = data[i] / 127.5 - 1 - mx,
          y = data[i + 1] / 127.5 - 1 - my;
        const z = Math.sqrt(Math.max(0, 1 - x * x - y * y)),
          l = Math.hypot(x, y, z) || 1;
        data[i] = Math.round((x / l + 1) * 127.5);
        data[i + 1] = Math.round((y / l + 1) * 127.5);
        data[i + 2] = Math.round((z / l + 1) * 127.5);
      }
    }
  }
  // never scale up: a 1024 source in a 2048 slot only costs bytes
  const k = Math.min(1, size / Math.max(info.width, info.height));
  const png = await sharp(data, {
    raw: { width: info.width, height: info.height, channels: 4 },
  })
    .resize(Math.round(info.width * k), Math.round(info.height * k), {
      kernel: "lanczos3",
    })
    .png()
    .toBuffer();
  const opts = isNormal
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
        isSetKTX2SRGBTransferFunc: true,
        imageDecoder: decoder,
      };
  const out = await encodeToKTX2(new Uint8Array(png), opts);
  tex.setImage(new Uint8Array(out)).setMimeType("image/ktx2");
  return [out.length, Math.round(Math.max(info.width, info.height) * k)];
}

async function run(file, tier) {
  const doc = await io.read(path.join(IN, file));
  const root = doc.getRoot();
  doc.createExtension(KHRTextureBasisu).setRequired(true);
  const rep = { file, tier, textures: {}, texBytes: 0 };
  for (const m of root.listMaterials()) {
    const name = m.getName().split(".")[0]; // Blender adds .001 to the second copy of a material
    m.setName(name);
    if (ALPHA.has(name)) m.setAlphaMode("MASK").setAlphaCutoff(0.5);
    else m.setAlphaMode("OPAQUE");
    const skin = name === "skin";
    const slots = [
      ["base", m.getBaseColorTexture(), false],
      ["normal", m.getNormalTexture(), true],
    ];
    for (const [slot, tex, isNormal] of slots) {
      if (!tex || tex.getMimeType() === "image/ktx2") continue;
      let size = isNormal ? 512 : 1024;
      if (tier === "high" && (skin || name === "tunic"))
        size = isNormal ? 1024 : 2048;
      if (tier === "high" && skin) size = 2048;
      // skin relief on std too (UX, art-direction 9.5: the high tier only gets sharper, it doesn't add things)
      if (tier === "std" && skin && isNormal) size = 1024;
      const [n, encoded] = await encodeTexture(tex, size, isNormal);
      rep.textures[`${name}.${slot}`] = {
        size: encoded,
        bytes: n,
        ...(isNormal ? { leanDeg: tex.getExtras().normalLeanDeg } : {}),
      };
      rep.texBytes += n;
    }
  }
  await doc.transform(
    prune({ keepAttributes: false }),
    dedup({
      propertyTypes: [
        PropertyType.ACCESSOR,
        PropertyType.MESH,
        PropertyType.TEXTURE,
      ],
    }),
    quantize({
      quantizePosition: 14,
      quantizeNormal: 8,
      quantizeTexcoord: 12,
      quantizeWeight: 8,
    }),
    meshopt({ encoder: MeshoptEncoder, level: "medium" }),
  );
  const outFile = path.join(OUT, file);
  await io.write(outFile, doc);
  rep.bytes = fs.statSync(outFile).size;
  rep.geoBytes = rep.bytes - rep.texBytes;
  let morphs = 0,
    verts = 0,
    tris = 0;
  for (const me of root.listMeshes())
    for (const p of me.listPrimitives()) {
      morphs = Math.max(morphs, p.listTargets().length);
      verts += p.getAttribute("POSITION").getCount();
      tris += (p.getIndices()?.getCount() ?? 0) / 3;
    }
  Object.assign(rep, {
    morphs,
    verts,
    tris,
    materials: root.listMaterials().length,
    joints: root.listSkins()[0]?.listJoints().length ?? 0,
    anims: root.listAnimations().map((a) => a.getName()),
  });
  return rep;
}

const plan = [
  ["talk_high.glb", "high"],
  ["talk_high_nomn.glb", "high"],
  ["talk_std.glb", "std"],
  ["talk_std_nomn.glb", "std"],
  ["walk.glb", "walk"],
  ["anims.glb", "anim"],
];
const all = [];
for (const [f, t] of plan) {
  if (!fs.existsSync(path.join(IN, f))) continue;
  const r = await run(f, t);
  all.push(r);
  console.log(JSON.stringify(r));
}
fs.writeFileSync(
  path.join(OUT, "compress_report.json"),
  JSON.stringify(all, null, 1),
);
