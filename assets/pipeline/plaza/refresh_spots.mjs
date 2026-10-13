// When only new spots on flat ground are added, reuse the already-verified navmesh; geometry, textures, bakes and nav
// bytes stay untouched.
// 平地に立ち位置を追加するだけのときは、検証済みのナビメッシュを再利用する。ジオメトリ、テクスチャ、ベイク、nav のバイトは変えない。
// node refresh_spots.mjs <old layout> <new layout> <nav.json> <scene.json>
// Changing existing spots, geometry or terrain needs the full build.sh. This tool refuses to guess heights on slopes or steps.
// 既存の立ち位置・ジオメトリ・地形を変えるときは build.sh でフルビルドする。このツールは坂や段差の上の高さを推測しない。
import fs from "node:fs";
import crypto from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";
import { planToWorld, pointInPolygon, yawOf } from "./frame.mjs";

const [, , beforePath, afterPath, navPath, scenePath] = process.argv;
if (!scenePath)
  throw new Error(
    "Needs four files: old layout, new layout, nav.json, scene.json / 旧 layout、新 layout、nav.json、scene.json の 4 ファイルが必要",
  );
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
  throw new Error(
    "The layout changed outside the spots; a full build is required / 立ち位置以外のレイアウトが変わっている。フルビルドが必要",
  );
if (scene.inputs.files[layoutKey] !== sha(beforePath))
  throw new Error(
    "The old layout does not match the manifest inputs / 旧レイアウトがマニフェストの入力と一致しない",
  );
for (const [file, hash] of Object.entries(scene.inputs.files)) {
  if (file !== layoutKey && sha(path.join(repo, file)) !== hash)
    throw new Error(`Input changed: ${file} / 入力が変わっている：${file}`);
}
const navFile = scene.files.find((f) => f.path === scene.nav.file);
if (
  !navFile ||
  navFile.sha256 !== sha(navPath) ||
  navFile.bytes !== fs.statSync(navPath).size
)
  throw new Error(
    "The navmesh does not match the manifest / ナビメッシュがマニフェストと一致しない",
  );
for (const [name, spot] of Object.entries(previousSpots)) {
  if (!isDeepStrictEqual(spot, nextSpots[name]))
    throw new Error(
      `Existing spot ${name} changed; a full build is required / 既存の立ち位置 ${name} が変わっている。フルビルドが必要`,
    );
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
  if (pi < 0)
    throw new Error(
      `Spot ${name} is not on the navmesh / 立ち位置 ${name} がナビメッシュ上にない`,
    );
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
    throw new Error(
      `Spot ${name} is not on verified flat ground, so the geometry height check cannot be skipped / 立ち位置 ${name} は検証済みの平地上にないため、ジオメトリの高さ検査を省略できない`,
    );
  const pos = [round(X), round(heights[0]), round(Z)];
  for (const [other, item] of Object.entries(scene.spots)) {
    if (
      item.place === place &&
      Math.hypot(pos[0] - item.pos[0], pos[2] - item.pos[2]) < 1.2
    )
      throw new Error(
        `Spot ${name} is less than 1.2 m from ${other} / 立ち位置 ${name} と ${other} の距離が 1.2 m 未満`,
      );
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
console.log(
  `Added ${added} spots on flat ground; navmesh, geometry and texture bytes keep their hashes. / 平地の立ち位置を ${added} 件追加。ナビメッシュ・ジオメトリ・テクスチャのバイトはハッシュを保ったまま。`,
);
