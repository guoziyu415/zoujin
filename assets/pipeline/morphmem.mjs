// GPU bytes three.js uses for morph targets: per geometry, vertices x targets x (position[, normal]) x RGBA32F
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { MeshoptDecoder } from "meshoptimizer";
await MeshoptDecoder.ready;
const io = new NodeIO()
  .registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({ "meshopt.decoder": MeshoptDecoder });
for (const f of process.argv.slice(2)) {
  const doc = await io.read(f);
  let tot = 0;
  const parts = [];
  for (const m of doc.getRoot().listMeshes())
    for (const p of m.listPrimitives()) {
      const t = p.listTargets();
      if (!t.length) continue;
      const n = p.getAttribute("POSITION").getCount(),
        k = t[0].getAttribute("NORMAL") ? 2 : 1;
      const b = n * t.length * k * 16;
      tot += b;
      parts.push(`${m.getName()} ${n}v ${(b / 1048576).toFixed(1)}MB`);
    }
  console.log(
    f.split("/").pop(),
    (tot / 1048576).toFixed(1),
    "MB |",
    parts.join(", "),
  );
}
