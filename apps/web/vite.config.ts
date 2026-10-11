// Vite for the web front end (frontend-design 3). Besides React, the 3D layer needs a scene's generated files at
// /scenes/<slug>/ (not in git; scene-dir.ts says where they are): served in dev and preview, copied into dist on build.
// three's KTX2Loader brings its Basis transcoder itself (new URL(..., import.meta.url)), so Vite hashes it into assets.
// The API (/v1, its WebSocket, B-1's /__mock controls and the prerecorded voice files) goes to the mock or a local
// backend on ZOUJIN_API (default B-1's port); the Host header passes through so the server's Origin check holds.
import babel from "@rolldown/plugin-babel";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
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

// React Compiler on the screens and the HUD; not on the 3D layer (react-three-fiber frames, and the 3D chunk's budget)
const compiler = reactCompilerPreset();
compiler.rolldown.filter = {
  ...compiler.rolldown.filter,
  id: { exclude: /\/src\/(three\/|screens\/(World|Measure)Screen)/ },
};

const API = process.env.ZOUJIN_API ?? "http://127.0.0.1:8787";
const proxy = {
  "/v1": { target: API, ws: true },
  "/__mock": { target: API },
  "/assets/voice": { target: API },
};

export default defineConfig({
  plugins: [react(), babel({ presets: [compiler] }), runtimeFiles()],
  build: { manifest: true, target: "es2022" },
  server: { host: "127.0.0.1", proxy },
  preview: { host: "127.0.0.1", proxy },
});
