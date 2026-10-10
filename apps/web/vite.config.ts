// Vite for the web front end (frontend-design 3). Besides React, the 3D layer needs a scene's generated files at
// /scenes/<slug>/ (not in git; scene-dir.ts says where they are): served in dev and preview, copied into dist on build.
// three's KTX2Loader brings its Basis transcoder itself (new URL(..., import.meta.url)), so Vite hashes it into assets.
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";
import type { Connect, Plugin } from "vite";
import { defineConfig } from "vite";
import { sceneDir } from "./scene-dir.ts";

const SCENES = ["syracuse-square"];
const TYPES: Record<string, string> = {
  ".json": "application/json",
  ".glb": "model/gltf-binary",
  ".ktx2": "image/ktx2",
};

// URL path under a mount -> file, refusing anything that climbs out of the directory
function resolveUnder(dir: string, rel: string): string | null {
  const file = path.resolve(dir, decodeURIComponent(rel.split("?")[0] ?? ""));
  return file.startsWith(dir + path.sep) &&
    fs.existsSync(file) &&
    fs.statSync(file).isFile()
    ? file
    : null;
}

function runtimeFiles(): Plugin {
  const mounts = (): [string, string][] =>
    SCENES.map((s) => [`/scenes/${s}/`, sceneDir(s)]);
  const serve: Connect.NextHandleFunction = (req, res, next) => {
    for (const [prefix, dir] of mounts()) {
      if (!req.url?.startsWith(prefix)) continue;
      const file = resolveUnder(dir, req.url.slice(prefix.length));
      if (!file) break;
      res.setHeader(
        "Content-Type",
        TYPES[path.extname(file)] ?? "application/octet-stream",
      );
      fs.createReadStream(file).pipe(res);
      return;
    }
    next();
  };
  let outDir = "dist";
  return {
    name: "zoujin-runtime-files",
    configResolved(c) {
      outDir = path.resolve(c.root, c.build.outDir);
    },
    configureServer(server) {
      server.middlewares.use(serve);
    },
    configurePreviewServer(server) {
      server.middlewares.use(serve);
    },
    closeBundle() {
      if (process.env.VITEST) return;
      for (const [prefix, dir] of mounts()) {
        if (!fs.existsSync(dir)) {
          this.warn(
            `${dir} missing: run assets/pipeline/plaza/build.sh (dist has no ${prefix})`,
          );
          continue;
        }
        fs.cpSync(dir, path.join(outDir, prefix), {
          recursive: true,
          filter: (f) => !f.endsWith(".md"),
        });
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), runtimeFiles()],
  build: { manifest: true, target: "es2022" },
  server: { host: "127.0.0.1" },
  preview: { host: "127.0.0.1" },
});
