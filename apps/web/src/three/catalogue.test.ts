// Every three.js element our JSX writes (<mesh>, <pointLight>, …) is in catalogue.ts: the build registers only those
// with r3f, so one missing renders nothing but an error in the built game (vite.config.ts threeCatalogue).
import fs from "node:fs";
import path from "node:path";
import * as THREE from "three";
import { describe, expect, it } from "vitest";
import * as catalogue from "./catalogue";

const src = path.resolve(import.meta.dirname, "..");
// SVG in the screens whose names three.js also has
const SVG = new Set(["path", "line"]);

function tsx(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return tsx(p);
    return p.endsWith(".tsx") ? [p] : [];
  });
}

describe("three catalogue", () => {
  it("lists every three.js element in src/", () => {
    const used = new Set<string>();
    for (const f of tsx(src))
      for (const m of fs.readFileSync(f, "utf8").matchAll(/<([a-z]\w*)/g)) {
        if (SVG.has(m[1]!)) continue;
        const name = m[1]![0]!.toUpperCase() + m[1]!.slice(1);
        if (name in THREE) used.add(name);
      }
    expect(used.size).toBeGreaterThan(0);
    expect([...used].filter((n) => !(n in catalogue))).toEqual([]);
  });
});
