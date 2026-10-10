import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { MeshoptDecoder } from "meshoptimizer";
await MeshoptDecoder.ready;
const io = new NodeIO()
  .registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({ "meshopt.decoder": MeshoptDecoder });
const doc = await io.read(process.argv[2]);
const r = doc.getRoot();
console.log(
  "ext",
  r.listExtensionsUsed().map((e) => e.extensionName),
);
for (const m of r.listMeshes()) {
  const p = m.listPrimitives();
  console.log(
    "mesh",
    m.getName(),
    p.length,
    "targets",
    p[0].listTargets().length,
    "names",
    JSON.stringify(m.getExtras()).slice(0, 200),
    "mat",
    p.map((x) => x.getMaterial()?.getName()),
  );
}
for (const n of r.listNodes())
  if (n.getMesh())
    console.log("node", n.getName(), n.getSkin() ? "skinned" : "");
const sk = r.listSkins()[0];
if (sk)
  console.log(
    "joints",
    sk
      .listJoints()
      .map((j) => j.getName())
      .join(" "),
  );
for (const a of r.listAnimations())
  console.log(
    "anim",
    a.getName(),
    a.listChannels().length,
    a
      .listChannels()
      .slice(0, 3)
      .map((c) => c.getTargetNode()?.getName() + "." + c.getTargetPath()),
  );
