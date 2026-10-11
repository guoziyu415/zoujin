// 仅新增平地站位时，复用已校验的导航网格；不改几何、贴图、烘焙或 nav 字节。
// node refresh_spots.mjs <旧 layout> <新 layout> <nav.json> <scene.json>
// 改已有站位/几何/地形请走完整 build.sh。本工具拒绝在斜坡/台阶上猜高度。
import fs from "node:fs";
import crypto from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";
import { planToWorld, pointInPolygon, yawOf } from "./frame.mjs";

const [, , beforePath, afterPath, navPath, scenePath] = process.argv;
if (!scenePath)
  throw new Error("需要旧 layout、新 layout、nav.json、scene.json 四个文件");
const read = (p) => JSON.parse(fs.readFileSync(p, "utf8"));
const sha = (p) =>
  crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");
const before = read(beforePath),
  after = read(afterPath),
  nav = read(navPath),
  scene = read(scenePath);
const repo = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../..",
);
const layoutKey = path.relative(repo, path.resolve(afterPath));
const { spots: previousSpots, ...previousRest } = before;
const { spots: nextSpots, ...nextRest } = after;
if (!isDeepStrictEqual(previousRest, nextRest))
  throw new Error("非站位布局有改动，必须完整构建");
if (scene.inputs.files[layoutKey] !== sha(beforePath))
  throw new Error("旧布局与清单输入不符");
for (const [file, hash] of Object.entries(scene.inputs.files)) {
  if (file !== layoutKey && sha(path.join(repo, file)) !== hash)
    throw new Error(`输入已变动：${file}`);
}
const navFile = scene.files.find((f) => f.path === scene.nav.file);
if (
  !navFile ||
  navFile.sha256 !== sha(navPath) ||
  navFile.bytes !== fs.statSync(navPath).size
)
  throw new Error("导航网格与清单不符");
for (const [name, spot] of Object.entries(previousSpots)) {
  if (!isDeepStrictEqual(spot, nextSpots[name]))
    throw new Error(`已有站位 ${name} 变动，必须完整构建`);
}
const round = (v) => Math.round(v * 100) / 100;
let added = 0;
for (const [name, spot] of Object.entries(nextSpots)) {
  if (previousSpots[name]) continue;
  const [X, , Z] = planToWorld(...spot.at, 0, after.rotationDeg);
  const [FX, , FZ] = planToWorld(...spot.face, 0, after.rotationDeg);
  const pi = nav.polys.findIndex((vs) =>
    pointInPolygon(
      X,
      Z,
      vs.map((v) => [nav.verts[v * 3], nav.verts[v * 3 + 2]]),
    ),
  );
  if (pi < 0) throw new Error(`站位 ${name} 不在导航网格内`);
  const place = nav.places[nav.place[pi]];
  const want =
    after.places.find((p) => pointInPolygon(...spot.at, p.polygon))?.id ??
    after.defaultPlace;
  if (place !== want) throw new Error(`站位 ${name} 地点归属不符`);
  const [first, count] = nav.detail.polyTris[pi];
  const heights = [];
  for (let i = first; i < first + count; i++) {
    const tri = nav.detail.tris.slice(i * 9, (i + 1) * 9);
    if (
      pointInPolygon(X, Z, [
        [tri[0], tri[2]],
        [tri[3], tri[5]],
        [tri[6], tri[8]],
      ])
    )
      heights.push(tri[1], tri[4], tri[7]);
  }
  if (!heights.length || Math.max(...heights) - Math.min(...heights) > 0.001)
    throw new Error(`站位 ${name} 不在已验证平地上，不能跳过几何高度检查`);
  const pos = [round(X), round(heights[0]), round(Z)];
  for (const [other, item] of Object.entries(scene.spots)) {
    if (
      item.place === place &&
      Math.hypot(pos[0] - item.pos[0], pos[2] - item.pos[2]) < 1.2
    )
      throw new Error(`站位 ${name} 离 ${other} 不足 1.2 米`);
  }
  scene.spots[name] = {
    pos,
    yaw: +yawOf(FX - X, FZ - Z).toFixed(4),
    place,
    poly: pi,
    ...(spot.auto === false ? { auto: false } : {}),
  };
  added++;
}
scene.inputs.files[layoutKey] = sha(afterPath);
fs.writeFileSync(scenePath, JSON.stringify(scene, null, 1) + "\n");
console.log(`新增 ${added} 个平地站位，导航网格/几何/贴图字节保持原 hash。`);
