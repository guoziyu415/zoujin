// No two modules in one folder whose names differ only in case (Interior.tsx and interior.ts): on the Mac's
// case-insensitive disk "./Interior" finds the other one and the build breaks, while Linux builds it fine.
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const src = path.resolve(import.meta.dirname);

function clashes(dir: string): string[] {
  const seen = new Map<string, string>();
  const out: string[] = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.isDirectory()) {
      out.push(...clashes(path.join(dir, e.name)));
      continue;
    }
    // the module name an import writes (tests are never imported)
    if (!/\.[cm]?[jt]sx?$/.test(e.name) || /\.test\./.test(e.name)) continue;
    const stem = e.name.replace(/\.[cm]?[jt]sx?$/, "");
    const prev = seen.get(stem.toLowerCase());
    if (prev === undefined) seen.set(stem.toLowerCase(), stem);
    else if (prev !== stem)
      out.push(`${path.relative(src, dir)}: ${prev} / ${stem}`);
  }
  return out;
}

describe("module names", () => {
  it("never differ only in case within a folder", () => {
    expect(clashes(src)).toEqual([]);
  });
});
