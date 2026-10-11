// The crowd pack (F-4 range 1): the three bodies from MPFB 2 that assets/pipeline/crowd/build.sh writes into the scene's
// pack as crowd/crowd.json (the bones, each body's joints, where its arrays sit) and crowd/crowd.bin (the arrays,
// laid out as crowd.json "layout" says). Read straight into buffer attributes: no glTF loader in this chunk.
import { BufferAttribute, InstancedBufferGeometry } from "three";
import type { Costume } from "./bodies";
import { packSkeleton, type Skeleton } from "./rig";

type Vec3 = [number, number, number];
type Entry = {
  vertices: number;
  offset: number;
  indices: number;
  indexOffset: number;
  joints: Vec3[];
};
export type CrowdPackJson = {
  format: string;
  bones: { name: string; parent: number }[];
  costumes: Record<Costume, Entry>;
  bytes: number;
};

export type CrowdPack = Record<
  Costume,
  { geometry: InstancedBufferGeometry; skeleton: Skeleton }
>;

export function parseCrowdPack(
  json: CrowdPackJson,
  bin: ArrayBuffer,
): CrowdPack {
  if (json.format !== "zoujin-crowd-1" || bin.byteLength !== json.bytes)
    throw new Error("crowd pack: unknown format or size");
  const out = {} as CrowdPack;
  for (const [costume, c] of Object.entries(json.costumes) as [
    Costume,
    Entry,
  ][]) {
    const n = c.vertices;
    let at = c.offset;
    const take = <T>(
      make: (b: ArrayBuffer, o: number, len: number) => T,
      bytes: number,
      len: number,
    ): T => {
      const v = make(bin, at, len);
      at += bytes * len;
      return v;
    };
    const position = take((b, o, l) => new Float32Array(b, o, l), 4, n * 3);
    const padded = take((b, o, l) => new Int16Array(b, o, l), 2, n * 4); // x, y, z, pad
    const normal = new Int16Array(n * 3);
    for (let i = 0; i < n; i++)
      normal.set(padded.subarray(i * 4, i * 4 + 3), i * 3);
    const skinIndex = take((b, o, l) => new Uint8Array(b, o, l), 1, n * 4);
    const skinWeight = take((b, o, l) => new Uint8Array(b, o, l), 1, n * 4);
    const part = take((b, o, l) => new Uint8Array(b, o, l), 1, n);
    const g = new InstancedBufferGeometry();
    g.setAttribute("position", new BufferAttribute(position, 3));
    g.setAttribute("normal", new BufferAttribute(normal, 3, true));
    g.setAttribute("skinIndex", new BufferAttribute(skinIndex, 4));
    g.setAttribute("skinWeight", new BufferAttribute(skinWeight, 4, true));
    g.setAttribute("aPart", new BufferAttribute(part, 1));
    g.setIndex(
      new BufferAttribute(new Uint16Array(bin, c.indexOffset, c.indices), 1),
    );
    out[costume] = {
      geometry: g,
      skeleton: packSkeleton(json.bones, c.joints),
    };
  }
  return out;
}

// the scene's crowd, or null when its pack has none (the stand-ins then)
export async function loadCrowdPack(base: string): Promise<CrowdPack | null> {
  const res = await fetch(`${base}crowd/crowd.json`);
  if (!res.ok) return null;
  let json: CrowdPackJson;
  try {
    json = (await res.json()) as CrowdPackJson;
  } catch {
    return null; // a server that answers a missing file with the app's page
  }
  const bin = await fetch(`${base}crowd/crowd.bin`);
  if (!bin.ok) return null;
  return parseCrowdPack(json, await bin.arrayBuffer());
}
