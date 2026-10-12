// Repair the default morph weights in existing GLBs without recompressing geometry/textures.
// node neutralize_morphs.mjs <build_dir>
// The binary chunk is copied byte for byte. Re-run check_cast.mjs to refresh hashes after repair.
import fs from "node:fs";
import path from "node:path";

const root = process.argv[2];
if (!root) throw new Error("Usage: neutralize_morphs.mjs <build_dir>");
for (const dir of fs.readdirSync(root, { withFileTypes: true })) {
  if (!dir.isDirectory() || dir.name.startsWith(".")) continue;
  for (const tier of ["talk_high", "talk_std"]) {
    const file = path.join(root, dir.name, `${tier}.glb`);
    if (!fs.existsSync(file)) continue;
    const bytes = fs.readFileSync(file);
    if (bytes.readUInt32LE(0) !== 0x46546c67 || bytes.readUInt32LE(4) !== 2)
      throw new Error(`Invalid GLB: ${file}`);
    const length = bytes.readUInt32LE(12);
    if (bytes.readUInt32LE(16) !== 0x4e4f534a)
      throw new Error(`First chunk is not JSON: ${file}`);
    const json = JSON.parse(bytes.subarray(20, 20 + length).toString("utf8"));
    let count = 0;
    for (const item of [...(json.meshes ?? []), ...(json.nodes ?? [])]) {
      if (!item.weights) continue;
      count += item.weights.filter((weight) => weight !== 0).length;
      item.weights.fill(0);
    }
    if (!count) continue;
    const encoded = Buffer.from(JSON.stringify(json));
    const jsonLength = Math.ceil(encoded.length / 4) * 4;
    const binaryChunks = bytes.subarray(20 + length);
    const output = Buffer.alloc(20 + jsonLength + binaryChunks.length, 0x20);
    bytes.copy(output, 0, 0, 20);
    output.writeUInt32LE(output.length, 8);
    output.writeUInt32LE(jsonLength, 12);
    encoded.copy(output, 20);
    binaryChunks.copy(output, 20 + jsonLength);
    fs.writeFileSync(file, output);
    console.log(`${dir.name}/${tier}: cleared ${count} default morph weights`);
  }
}
