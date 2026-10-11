// The near follow camera's zones (F-11 card 6: inside Melos's house) from layout.json into the packed scene.json,
// polygons turned into glTF x, z as the spots are (../plaza/frame.mjs). The page reads scene.json cameraZones
// (apps/web/src/three/village/zones.ts).
//   node zones.mjs <layout.json> <pack dir>
import fs from "fs";
import path from "path";
import { planToWorld } from "../plaza/frame.mjs";

const [, , LAYOUT, DIR] = process.argv;
const layout = JSON.parse(fs.readFileSync(LAYOUT, "utf8"));
const file = path.join(DIR, "scene.json");
const scene = JSON.parse(fs.readFileSync(file, "utf8"));
scene.cameraZones = (layout.cameraZones ?? []).map(({ about: _, ...z }) => ({
  ...z,
  polygon: z.polygon.map(([x, y]) => {
    const [X, , Z] = planToWorld(x, y, 0, layout.rotationDeg);
    return [X, Z];
  }),
}));
fs.writeFileSync(file, JSON.stringify(scene, null, 1) + "\n");
console.log(
  `camera zones: ${scene.cameraZones.map((z) => z.id).join(", ") || "none"}`,
);
