// The scene's navmesh (nav.json from assets/pipeline/plaza/nav.mjs): A* over the polygons, then the funnel ("simple
// stupid funnel", Mononen) through the shared edges, and ground height from the detail triangles (frontend-design 8.4,
// 8.6). No Detour and no WASM: the plaza has about 150 polygons, a path is well under a millisecond.

export type NavData = {
  version: 1;
  agent: { radius: number; height: number; climb: number; slopeDeg: number };
  cellSize: number;
  places: string[];
  verts: number[]; // x, y, z per vertex, glTF metres
  polys: number[][]; // vertex indices, convex
  neis: number[][]; // neis[i][j] = polygon across edge j (vs[j] -> vs[j + 1]) or -1
  place: number[]; // index into places
  detail: { tris: number[]; polyTris: [number, number][] }; // 9 numbers per triangle; [first, count] per polygon
};

export type NavPoint = { poly: number; x: number; y: number; z: number };
type P2 = { x: number; z: number };

// Mononen's triarea2: > 0 when c is to the right of a -> b (the funnel's "right" side)
const triarea2 = (a: P2, b: P2, c: P2) =>
  (c.x - a.x) * (b.z - a.z) - (b.x - a.x) * (c.z - a.z);
const same = (a: P2, b: P2) =>
  Math.abs(a.x - b.x) < 1e-6 && Math.abs(a.z - b.z) < 1e-6;

function closestOnSegment(p: P2, a: P2, b: P2): P2 {
  const dx = b.x - a.x;
  const dz = b.z - a.z;
  const l2 = dx * dx + dz * dz;
  const t =
    l2 > 0
      ? Math.min(1, Math.max(0, ((p.x - a.x) * dx + (p.z - a.z) * dz) / l2))
      : 0;
  return { x: a.x + dx * t, z: a.z + dz * t };
}

export class NavMesh {
  readonly data: NavData;
  private readonly centre: P2[];
  private readonly box: [number, number, number, number][]; // minX, minZ, maxX, maxZ
  private blocked = new Set<number>(); // place indices whose polygons are out of bounds (places[].enabled = false)

  constructor(data: NavData) {
    this.data = data;
    this.centre = data.polys.map((vs) => {
      let x = 0;
      let z = 0;
      for (const v of vs) {
        x += this.vx(v);
        z += this.vz(v);
      }
      return { x: x / vs.length, z: z / vs.length };
    });
    this.box = data.polys.map((vs) => {
      const b: [number, number, number, number] = [
        Infinity,
        Infinity,
        -Infinity,
        -Infinity,
      ];
      for (const v of vs) {
        b[0] = Math.min(b[0], this.vx(v));
        b[1] = Math.min(b[1], this.vz(v));
        b[2] = Math.max(b[2], this.vx(v));
        b[3] = Math.max(b[3], this.vz(v));
      }
      return b;
    });
  }

  private vx(i: number): number {
    return this.data.verts[3 * i]!;
  }
  private vy(i: number): number {
    return this.data.verts[3 * i + 1]!;
  }
  private vz(i: number): number {
    return this.data.verts[3 * i + 2]!;
  }
  private v2(i: number): P2 {
    return { x: this.vx(i), z: this.vz(i) };
  }

  get polyCount(): number {
    return this.data.polys.length;
  }

  placeOf(poly: number): string {
    return this.data.places[this.data.place[poly] ?? 0] ?? "";
  }

  // places whose polygons can't be walked on (the workshop while its gate is shut)
  setBlockedPlaces(ids: Iterable<string>): void {
    this.blocked = new Set(
      [...ids].map((id) => this.data.places.indexOf(id)).filter((i) => i >= 0),
    );
  }

  isOpen(poly: number): boolean {
    return (
      poly >= 0 &&
      poly < this.polyCount &&
      !this.blocked.has(this.data.place[poly] ?? 0)
    );
  }

  private inside(poly: number, x: number, z: number): boolean {
    const b = this.box[poly]!;
    if (
      x < b[0] - 1e-4 ||
      x > b[2] + 1e-4 ||
      z < b[1] - 1e-4 ||
      z > b[3] + 1e-4
    )
      return false;
    const vs = this.data.polys[poly]!;
    let sign = 0;
    for (let j = 0; j < vs.length; j++) {
      const a = this.v2(vs[j]!);
      const c = this.v2(vs[(j + 1) % vs.length]!);
      const s = triarea2(a, c, { x, z });
      if (Math.abs(s) < 1e-9) continue;
      if (sign === 0) sign = Math.sign(s);
      else if (Math.sign(s) !== sign) return false;
    }
    return true;
  }

  // ground height inside a polygon, from its detail triangles (the steps are slopes there)
  heightAt(poly: number, x: number, z: number): number {
    const [first, count] = this.data.detail.polyTris[poly] ?? [0, 0];
    const t = this.data.detail.tris;
    let best = Infinity;
    let bestY = 0;
    for (let k = first; k < first + count; k++) {
      const o = 9 * k;
      const ax = t[o]!;
      const ay = t[o + 1]!;
      const az = t[o + 2]!;
      const bx = t[o + 3]!;
      const by = t[o + 4]!;
      const bz = t[o + 5]!;
      const cx = t[o + 6]!;
      const cy = t[o + 7]!;
      const cz = t[o + 8]!;
      const det = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz);
      if (Math.abs(det) < 1e-12) continue;
      const l1 = ((bz - cz) * (x - cx) + (cx - bx) * (z - cz)) / det;
      const l2 = ((cz - az) * (x - cx) + (ax - cx) * (z - cz)) / det;
      const l3 = 1 - l1 - l2;
      const y = l1 * ay + l2 * by + l3 * cy;
      const out = Math.max(0, -l1, -l2, -l3); // 0 inside; the nearest triangle wins on the edges
      if (out < best) {
        best = out;
        bestY = y;
        if (out === 0) break;
      }
    }
    if (best < Infinity) return bestY;
    const vs = this.data.polys[poly] ?? [];
    return vs.reduce((s, v) => s + this.vy(v), 0) / Math.max(1, vs.length);
  }

  // the open polygon under (x, z); near yHint when polygons overlap in plan (none do in the plaza yet)
  locate(x: number, z: number, hintPoly = -1, yHint?: number): NavPoint | null {
    if (this.isOpen(hintPoly) && this.inside(hintPoly, x, z))
      return { poly: hintPoly, x, y: this.heightAt(hintPoly, x, z), z };
    if (hintPoly >= 0)
      for (const n of this.data.neis[hintPoly] ?? [])
        if (this.isOpen(n) && this.inside(n, x, z))
          return { poly: n, x, y: this.heightAt(n, x, z), z };
    let found: NavPoint | null = null;
    for (let p = 0; p < this.polyCount; p++) {
      if (!this.isOpen(p) || !this.inside(p, x, z)) continue;
      const y = this.heightAt(p, x, z);
      if (
        !found ||
        (yHint !== undefined && Math.abs(y - yHint) < Math.abs(found.y - yHint))
      )
        found = { poly: p, x, y, z };
      if (yHint === undefined) break;
    }
    return found;
  }

  // the nearest point on the open mesh (a tap just outside the walkable area still walks to its edge)
  nearest(x: number, z: number): NavPoint | null {
    const hit = this.locate(x, z);
    if (hit) return hit;
    let best: NavPoint | null = null;
    let bestD = Infinity;
    for (let p = 0; p < this.polyCount; p++) {
      if (!this.isOpen(p)) continue;
      const vs = this.data.polys[p]!;
      for (let j = 0; j < vs.length; j++) {
        const q = closestOnSegment(
          { x, z },
          this.v2(vs[j]!),
          this.v2(vs[(j + 1) % vs.length]!),
        );
        // a hair inside, so the point locates in this polygon
        const c = this.centre[p]!;
        const px = q.x + (c.x - q.x) * 1e-3;
        const pz = q.z + (c.z - q.z) * 1e-3;
        const d = (px - x) ** 2 + (pz - z) ** 2;
        if (d < bestD) {
          bestD = d;
          best = { poly: p, x: px, y: this.heightAt(p, px, pz), z: pz };
        }
      }
    }
    return best;
  }

  // A* over open polygons; edge midpoints as the nodes' positions
  private polyPath(from: NavPoint, to: NavPoint): number[] | null {
    if (from.poly === to.poly) return [from.poly];
    const n = this.polyCount;
    const g = new Float64Array(n).fill(Infinity);
    const parent = new Int32Array(n).fill(-1);
    const pos: P2[] = this.centre.map((c) => ({ ...c }));
    const closed = new Uint8Array(n);
    const open: number[] = [from.poly];
    g[from.poly] = 0;
    pos[from.poly] = { x: from.x, z: from.z };
    const h = (p: number) => Math.hypot(pos[p]!.x - to.x, pos[p]!.z - to.z);
    while (open.length) {
      let bi = 0;
      for (let i = 1; i < open.length; i++)
        if (g[open[i]!]! + h(open[i]!) < g[open[bi]!]! + h(open[bi]!)) bi = i;
      const cur = open.splice(bi, 1)[0]!;
      if (cur === to.poly) break;
      closed[cur] = 1;
      const vs = this.data.polys[cur]!;
      const ns = this.data.neis[cur]!;
      for (let j = 0; j < ns.length; j++) {
        const nb = ns[j]!;
        if (nb < 0 || closed[nb] || !this.isOpen(nb)) continue;
        const a = this.v2(vs[j]!);
        const b = this.v2(vs[(j + 1) % vs.length]!);
        const mid =
          nb === to.poly
            ? { x: to.x, z: to.z }
            : { x: (a.x + b.x) / 2, z: (a.z + b.z) / 2 };
        const cost =
          g[cur]! + Math.hypot(mid.x - pos[cur]!.x, mid.z - pos[cur]!.z);
        if (cost < g[nb]!) {
          g[nb] = cost;
          parent[nb] = cur;
          pos[nb] = mid;
          if (!open.includes(nb)) open.push(nb);
        }
      }
    }
    if (parent[to.poly] === -1) return null;
    const path = [to.poly];
    while (path[0] !== from.poly) path.unshift(parent[path[0]!]!);
    return path;
  }

  // shared edge of two neighbouring polygons as [left, right] for someone walking from a into b
  private portal(a: number, b: number): [P2, P2] {
    const vs = this.data.polys[a]!;
    const j = this.data.neis[a]!.indexOf(b);
    const p = this.v2(vs[j]!);
    const q = this.v2(vs[(j + 1) % vs.length]!);
    const c = this.centre[a]!;
    const mid = { x: (p.x + q.x) / 2, z: (p.z + q.z) / 2 };
    return triarea2(c, mid, p) > 0 ? [q, p] : [p, q];
  }

  // straight-line path on the mesh, start and end included; null when the goal can't be reached
  findPath(from: NavPoint, to: NavPoint): NavPoint[] | null {
    const polys = this.polyPath(from, to);
    if (!polys) return null;
    const s = { x: from.x, z: from.z };
    const e = { x: to.x, z: to.z };
    const portals: [P2, P2][] = [[s, s]];
    const portalPoly: number[] = [from.poly];
    for (let i = 0; i + 1 < polys.length; i++) {
      portals.push(this.portal(polys[i]!, polys[i + 1]!));
      portalPoly.push(polys[i + 1]!);
    }
    portals.push([e, e]);
    portalPoly.push(to.poly);

    const pts: { p: P2; poly: number }[] = [{ p: s, poly: from.poly }];
    let apex = s;
    let left = s;
    let right = s;
    let leftI = 0;
    let rightI = 0;
    for (let i = 1; i < portals.length; i++) {
      const [l, r] = portals[i]!;
      if (triarea2(apex, right, r) <= 0) {
        if (same(apex, right) || triarea2(apex, left, r) > 0) {
          right = r;
          rightI = i;
        } else {
          pts.push({ p: left, poly: portalPoly[leftI]! });
          const apexI = leftI; // restart the scan from the new apex
          apex = left;
          left = right = apex;
          leftI = rightI = apexI;
          i = apexI;
          continue;
        }
      }
      if (triarea2(apex, left, l) >= 0) {
        if (same(apex, left) || triarea2(apex, right, l) < 0) {
          left = l;
          leftI = i;
        } else {
          pts.push({ p: right, poly: portalPoly[rightI]! });
          const apexI = rightI; // restart the scan from the new apex
          apex = right;
          left = right = apex;
          leftI = rightI = apexI;
          i = apexI;
          continue;
        }
      }
    }
    if (!same(pts[pts.length - 1]!.p, e)) pts.push({ p: e, poly: to.poly });
    return pts.map(({ p, poly }) => {
      // corners sit on polygon edges: pick whichever neighbouring polygon contains them for the height
      const at = this.locate(p.x, p.z, poly) ?? {
        poly,
        x: p.x,
        y: this.heightAt(poly, p.x, p.z),
        z: p.z,
      };
      return at;
    });
  }

  // one step for the keys or the stick: go straight if the mesh is there, else slide along the wall that stops us
  moveBy(from: NavPoint, dx: number, dz: number): NavPoint {
    const direct = this.locate(from.x + dx, from.z + dz, from.poly, from.y);
    if (
      direct &&
      Math.abs(direct.y - from.y) <= this.data.agent.climb + Math.hypot(dx, dz)
    )
      return direct;
    // the boundary edge of the current polygon that the step crosses
    const vs = this.data.polys[from.poly]!;
    const ns = this.data.neis[from.poly]!;
    const to = { x: from.x + dx, z: from.z + dz };
    for (let j = 0; j < vs.length; j++) {
      const nb = ns[j]!;
      if (nb >= 0 && this.isOpen(nb)) continue;
      const a = this.v2(vs[j]!);
      const b = this.v2(vs[(j + 1) % vs.length]!);
      const sa = triarea2(a, b, from);
      const sb = triarea2(a, b, to);
      if (Math.sign(sa) === Math.sign(sb)) continue;
      const ex = b.x - a.x;
      const ez = b.z - a.z;
      const el = Math.hypot(ex, ez) || 1;
      const along = (dx * ex + dz * ez) / el;
      const slide = this.locate(
        from.x + (ex / el) * along * 0.98,
        from.z + (ez / el) * along * 0.98,
        from.poly,
        from.y,
      );
      if (slide) return slide;
    }
    return from;
  }
}
