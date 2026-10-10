// Navmesh for one scene with recast (WASM, build time only). The page does its own A* + funnel on the result
// (frontend-design 8.6, 9.4), so this writes a plain polygon list instead of Detour's binary format.
// - only the walkable polygons of layout.json are kept (spans outside them are cleared before erosion), so the
//   castle steps behind the wall or the strip north of the houses never become walkable;
// - recast areas carry the place: 63 (RC_WALKABLE_AREA) = layout.defaultPlace, 1.. = layout.places[i - 1];
// - polygons not connected to the player's start spot are dropped; every spot must land on the mesh.
import {
  init,
  Recast,
  RecastBuildContext,
  VerticesArray,
  TrianglesArray,
  TriangleAreasArray,
  FloatArray,
  calcGridSize,
  allocHeightfield,
  createHeightfield,
  markWalkableTriangles,
  rasterizeTriangles,
  filterLowHangingWalkableObstacles,
  filterLedgeSpans,
  filterWalkableLowHeightSpans,
  allocCompactHeightfield,
  buildCompactHeightfield,
  markBoxArea,
  markConvexPolyArea,
  erodeWalkableArea,
  buildDistanceField,
  buildRegions,
  allocContourSet,
  buildContours,
  allocPolyMesh,
  buildPolyMesh,
  allocPolyMeshDetail,
  buildPolyMeshDetail,
} from "recast-navigation";
import { planToWorld, worldToPlan, yawOf, pointInPolygon } from "./frame.mjs";

// agent: a person (frontend-design 8.3); steps are 0.38 m, the castle steps 4 x 0.38 m
export const AGENT = { radius: 0.3, height: 1.8, climb: 0.4, slopeDeg: 40 };
const CS = 0.15;
const CH = 0.05;
const r2 = (v) => Math.round(v * 100) / 100;

export function buildNav(meshes, layout) {
  return init().then(() => build(meshes, layout));
}

async function build(meshes, layout) {
  const ROT = layout.rotationDeg;
  const errors = [];
  const warnings = [];
  // ---- input soup
  let nv = 0;
  const pos = [];
  const tri = [];
  for (const { pos: p, idx } of meshes) {
    for (let i = 0; i < p.length; i++) pos.push(p[i]);
    for (let i = 0; i < idx.length; i++) tri.push(idx[i] + nv);
    nv += p.length / 3;
  }
  const bmin = [Infinity, Infinity, Infinity];
  const bmax = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < pos.length; i++) {
    bmin[i % 3] = Math.min(bmin[i % 3], pos[i]);
    bmax[i % 3] = Math.max(bmax[i % 3], pos[i]);
  }
  bmin[1] -= 0.5;
  bmax[1] += AGENT.height;
  const ctx = new RecastBuildContext();
  const verts = new VerticesArray();
  verts.copy(pos);
  const tris = new TrianglesArray();
  tris.copy(tri);
  const nt = tri.length / 3;
  const { width, height } = calcGridSize(bmin, bmax, CS);
  const vox = {
    height: Math.ceil(AGENT.height / CH),
    climb: Math.floor(AGENT.climb / CH),
    radius: Math.ceil(AGENT.radius / CS),
  };

  const hf = allocHeightfield();
  if (!createHeightfield(ctx, hf, width, height, bmin, bmax, CS, CH))
    throw new Error("createHeightfield");
  const areas = new TriangleAreasArray();
  areas.resize(nt);
  markWalkableTriangles(ctx, AGENT.slopeDeg, verts, nv, tris, nt, areas);
  if (!rasterizeTriangles(ctx, verts, nv, tris, areas, nt, hf, vox.climb))
    throw new Error("rasterizeTriangles");
  filterLowHangingWalkableObstacles(ctx, vox.climb, hf);
  filterLedgeSpans(ctx, vox.height, vox.climb, hf);
  filterWalkableLowHeightSpans(ctx, vox.height, hf);
  const chf = allocCompactHeightfield();
  if (!buildCompactHeightfield(ctx, vox.height, vox.climb, hf, chf))
    throw new Error("buildCompactHeightfield");

  // ---- clear everything outside the walkable polygons, one box per run of cells in a grid row
  const walk = layout.walkable.map((w) => w.polygon);
  const inWalk = (X, Z) => {
    const [x, y] = worldToPlan(X, Z, ROT);
    return walk.some((p) => pointInPolygon(x, y, p));
  };
  let boxes = 0;
  for (let r = 0; r < height; r++) {
    const z = bmin[2] + (r + 0.5) * CS;
    let run = -1;
    for (let c = 0; c <= width; c++) {
      const out = c < width && !inWalk(bmin[0] + (c + 0.5) * CS, z);
      if (out && run < 0) run = c;
      if (!out && run >= 0) {
        markBoxArea(
          ctx,
          [bmin[0] + (run + 0.01) * CS, bmin[1], bmin[2] + (r + 0.01) * CS],
          [bmin[0] + (c - 1 + 0.99) * CS, bmax[1], bmin[2] + (r + 0.99) * CS],
          0,
          chf,
        );
        boxes++;
        run = -1;
      }
    }
  }
  if (!erodeWalkableArea(ctx, vox.radius, chf))
    throw new Error("erodeWalkableArea");

  // ---- places: convex polygons in plan coordinates (recast marks convex areas only)
  layout.places.forEach((pl, i) => {
    const P = pl.polygon;
    const turns = P.map(([ax, ay], k) => {
      const [bx, by] = P[(k + 1) % P.length];
      const [cx, cy] = P[(k + 2) % P.length];
      return Math.sign((bx - ax) * (cy - by) - (by - ay) * (cx - bx));
    }).filter((t) => t !== 0);
    if (!turns.every((t) => t === turns[0]))
      errors.push(`place ${pl.id}: polygon is not convex`);
    const w = pl.polygon.map(([x, y]) => planToWorld(x, y, 0, ROT));
    const fa = new FloatArray();
    fa.copy(w.flat());
    markConvexPolyArea(ctx, fa, w.length, bmin[1], bmax[1], i + 1, chf);
    fa.destroy();
  });
  if (!buildDistanceField(ctx, chf)) throw new Error("buildDistanceField");
  if (!buildRegions(ctx, chf, 0, 8 * 8, 20 * 20))
    throw new Error("buildRegions");
  const cset = allocContourSet();
  if (
    !buildContours(
      ctx,
      chf,
      1.3,
      Math.round(12 / CS),
      cset,
      Recast.RC_CONTOUR_TESS_WALL_EDGES,
    )
  )
    throw new Error("buildContours");
  const pm = allocPolyMesh();
  if (!buildPolyMesh(ctx, cset, 6, pm)) throw new Error("buildPolyMesh");
  const dm = allocPolyMeshDetail();
  if (!buildPolyMeshDetail(ctx, pm, chf, CS * 6, CH * 1, dm))
    throw new Error("buildPolyMeshDetail");

  // ---- recast heights sit a voxel or two above the floor (feet would float ~10 cm); snap every vertex down to the
  // highest upward-facing input triangle at most 0.45 m below it
  const G = 2;
  const grid = new Map();
  for (let t = 0; t < nt; t++) {
    const [a, b, c] = [tri[t * 3], tri[t * 3 + 1], tri[t * 3 + 2]].map((v) => [
      pos[v * 3],
      pos[v * 3 + 1],
      pos[v * 3 + 2],
    ]);
    const ny = (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]);
    const len = Math.hypot(
      (b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]),
      ny,
      (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]),
    );
    if (Math.abs(ny) < 0.5 * len) continue;
    const [x0, x1] = [
      Math.min(a[0], b[0], c[0]),
      Math.max(a[0], b[0], c[0]),
    ].map((v) => Math.floor(v / G));
    const [z0, z1] = [
      Math.min(a[2], b[2], c[2]),
      Math.max(a[2], b[2], c[2]),
    ].map((v) => Math.floor(v / G));
    for (let i = x0; i <= x1; i++)
      for (let k = z0; k <= z1; k++)
        (
          grid.get(`${i},${k}`) ?? grid.set(`${i},${k}`, []).get(`${i},${k}`)
        ).push([a, b, c]);
  }
  const snapY = (x, y, z) => {
    let best = null;
    for (const [a, b, c] of grid.get(
      `${Math.floor(x / G)},${Math.floor(z / G)}`,
    ) ?? []) {
      const d = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2]);
      const l1 = ((b[2] - c[2]) * (x - c[0]) + (c[0] - b[0]) * (z - c[2])) / d;
      const l2 = ((c[2] - a[2]) * (x - c[0]) + (a[0] - c[0]) * (z - c[2])) / d;
      const l3 = 1 - l1 - l2;
      if (l1 < -1e-5 || l2 < -1e-5 || l3 < -1e-5) continue;
      const h = l1 * a[1] + l2 * b[1] + l3 * c[1];
      if (h <= y + 0.02 && h >= y - 0.45 && (best === null || h > best))
        best = h;
    }
    return best ?? y;
  };

  // ---- read the poly mesh back
  const nvp = pm.nvp();
  const o = pm.bmin();
  const NONE = 0xffff;
  const vtx = [];
  for (let i = 0; i < pm.nverts(); i++) {
    const x = o.x + pm.verts(i * 3) * pm.cs();
    const z = o.z + pm.verts(i * 3 + 2) * pm.cs();
    vtx.push([x, snapY(x, o.y + pm.verts(i * 3 + 1) * pm.ch(), z), z]);
  }
  const polys = [];
  for (let i = 0; i < pm.npolys(); i++) {
    const b = i * 2 * nvp;
    const vs = [];
    const ns = [];
    for (let j = 0; j < nvp; j++) {
      const v = pm.polys(b + j);
      if (v === NONE) break;
      vs.push(v);
      const n = pm.polys(b + nvp + j);
      ns.push(n === NONE || n & 0x8000 ? -1 : n);
    }
    const area = pm.areas(i);
    const dmb = i * 4;
    const dt = [];
    const vb = dm.meshes(dmb);
    const tb = dm.meshes(dmb + 2);
    for (let t = 0; t < dm.meshes(dmb + 3); t++) {
      const k = (tb + t) * 4;
      dt.push(
        [0, 1, 2].map((q) => {
          const vi = vb + dm.tris(k + q);
          const [x, y, z] = [
            dm.verts(vi * 3),
            dm.verts(vi * 3 + 1),
            dm.verts(vi * 3 + 2),
          ];
          return [x, snapY(x, y, z), z];
        }),
      );
    }
    polys.push({
      vs,
      ns,
      place: area === Recast.RC_WALKABLE_AREA ? 0 : area,
      detail: dt,
    });
  }

  // ---- keep what can be reached from the player's start
  const placeIds = [layout.defaultPlace, ...layout.places.map((p) => p.id)];
  const xz = (v) => [vtx[v][0], vtx[v][2]];
  const inPoly = (p, X, Z) => pointInPolygon(X, Z, p.vs.map(xz));
  const spotWorld = (s) => planToWorld(s.at[0], s.at[1], 0, ROT);
  const start = layout.spots[layout.playerStartSpot];
  const [sx, , sz] = spotWorld(start);
  const s0 = polys.findIndex((p) => inPoly(p, sx, sz));
  if (s0 < 0)
    throw new Error(
      `player start spot ${layout.playerStartSpot} is not on the navmesh`,
    );
  const seen = new Int32Array(polys.length).fill(-1);
  const order = [s0];
  seen[s0] = 0;
  for (let k = 0; k < order.length; k++) {
    for (const n of polys[order[k]].ns) {
      if (n >= 0 && seen[n] < 0) {
        seen[n] = order.length;
        order.push(n);
      }
    }
  }
  if (order.length < polys.length)
    warnings.push(
      `dropped ${polys.length - order.length} unreachable polygons`,
    );
  const keep = order.slice().sort((a, b) => a - b);
  const remap = new Int32Array(polys.length).fill(-1);
  keep.forEach((p, i) => (remap[p] = i));
  const vmap = new Map();
  const outV = [];
  const vid = (v) => {
    if (!vmap.has(v)) {
      vmap.set(v, outV.length / 3);
      outV.push(r2(vtx[v][0]), r2(vtx[v][1]), r2(vtx[v][2]));
    }
    return vmap.get(v);
  };
  const outP = [];
  const outN = [];
  const outA = [];
  const dV = [];
  const dP = [];
  for (const pi of keep) {
    const p = polys[pi];
    outP.push(p.vs.map(vid));
    outN.push(p.ns.map((n) => (n >= 0 ? remap[n] : -1)));
    outA.push(p.place);
    dP.push([dV.length / 9, p.detail.length]);
    for (const t of p.detail)
      for (const v of t) dV.push(r2(v[0]), r2(v[1]), r2(v[2]));
  }

  // ---- spots: on the mesh, height from the detail triangles, facing from layout
  const kept = keep.map((pi) => polys[pi]);
  const heightAt = (p, X, Z) => {
    for (const [a, b, c] of p.detail) {
      const d = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2]);
      const l1 = ((b[2] - c[2]) * (X - c[0]) + (c[0] - b[0]) * (Z - c[2])) / d;
      const l2 = ((c[2] - a[2]) * (X - c[0]) + (a[0] - c[0]) * (Z - c[2])) / d;
      const l3 = 1 - l1 - l2;
      if (l1 >= -1e-4 && l2 >= -1e-4 && l3 >= -1e-4)
        return l1 * a[1] + l2 * b[1] + l3 * c[1];
    }
    return null;
  };
  // nearest point on the kept mesh (for spots that sit right against an obstacle, like the post)
  const nearest = (X, Z) => {
    let best = null;
    kept.forEach((p, i) => {
      const ring = p.vs.map(xz);
      if (pointInPolygon(X, Z, ring)) {
        best = { i, X, Z, d: 0 };
        return;
      }
      for (let j = 0; j < ring.length; j++) {
        const [ax, az] = ring[j];
        const [bx, bz] = ring[(j + 1) % ring.length];
        const ex = bx - ax;
        const ez = bz - az;
        const t = Math.max(
          0,
          Math.min(1, ((X - ax) * ex + (Z - az) * ez) / (ex * ex + ez * ez)),
        );
        const qx = ax + t * ex;
        const qz = az + t * ez;
        const d = Math.hypot(X - qx, Z - qz);
        if (!best || d < best.d) best = { i, X: qx, Z: qz, d };
      }
    });
    return best;
  };
  const spots = {};
  for (const [name, s] of Object.entries(layout.spots)) {
    const [X, , Z] = spotWorld(s);
    const hit = nearest(X, Z);
    if (!hit || hit.d > 0.6) {
      errors.push(
        `spot ${name} is ${hit ? hit.d.toFixed(2) + " m" : "far"} off the navmesh`,
      );
      continue;
    }
    if (hit.d > 0)
      warnings.push(
        `spot ${name} moved ${hit.d.toFixed(2)} m onto the navmesh`,
      );
    // pull a hair inside so the page's point-in-polygon test agrees
    const c = kept[hit.i].vs
      .map(xz)
      .reduce((a, [x, z]) => [a[0] + x, a[1] + z], [0, 0])
      .map((v) => v / kept[hit.i].vs.length);
    const px = hit.d > 0 ? hit.X + (c[0] - hit.X) * 0.02 : X;
    const pz = hit.d > 0 ? hit.Z + (c[1] - hit.Z) * 0.02 : Z;
    const yd =
      heightAt(kept[hit.i], px, pz) ??
      kept[hit.i].vs.reduce((a, v) => a + vtx[v][1], 0) / kept[hit.i].vs.length;
    const y = snapY(px, yd, pz); // the detail mesh turns steps into ramps; a spot stands on the real step
    const [FX, , FZ] = planToWorld(s.face[0], s.face[1], 0, ROT);
    const place = placeIds[kept[hit.i].place];
    const want =
      layout.places.find((p) => pointInPolygon(s.at[0], s.at[1], p.polygon))
        ?.id ?? layout.defaultPlace;
    if (place !== want)
      errors.push(
        `spot ${name}: navmesh says ${place}, layout polygons say ${want}`,
      );
    spots[name] = {
      pos: [r2(px), r2(y), r2(pz)],
      yaw: +yawOf(FX - px, FZ - pz).toFixed(4),
      place,
      poly: hit.i,
      // only an explicit placement stands someone here; the automatic one skips it, as it skips way.*
      ...(s.auto === false ? { auto: false } : {}),
    };
  }
  for (const e of layout.exits) {
    if (!spots[e.spot])
      errors.push(`exit to ${e.place} names spot ${e.spot}, which is missing`);
  }
  for (const [i, id] of placeIds.entries()) {
    if (!outA.includes(i)) errors.push(`place ${id} has no walkable polygon`);
    const s = layout.startSpots?.[id];
    if (!s) errors.push(`place ${id} has no start spot (layout.startSpots)`);
    else if (spots[s] && spots[s].place !== id)
      errors.push(`start spot ${s} of ${id} lies in ${spots[s].place}`);
    else if (!spots[s]) errors.push(`start spot ${s} of ${id} is missing`);
  }
  if (layout.startSpots?.[layout.defaultPlace] !== layout.playerStartSpot)
    errors.push("playerStartSpot must be the start spot of the default place");

  const json = {
    version: 1,
    about:
      "Polygons for the page's A* + funnel; glTF metres. polys[i] = vertex indices (convex, CCW seen from +Y), neis[i][j] = polygon across edge j (vs[j] -> vs[j+1]) or -1, place[i] indexes places. detail.tris: 9 numbers per triangle, detail.polyTris[i] = [first triangle, count] of polygon i, for the ground height.",
    agent: AGENT,
    cellSize: CS,
    places: placeIds,
    verts: outV,
    polys: outP,
    neis: outN,
    place: outA,
    detail: { tris: dV, polyTris: dP },
  };
  return {
    json,
    spots,
    errors,
    warnings,
    stats: { boxes, width, height, polys: outP.length },
  };
}
