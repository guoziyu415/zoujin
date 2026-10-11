// Vite for the web front end (frontend-design 3). Besides React, the 3D layer needs a scene's generated files at
// /scenes/<slug>/ (not in git; scene-dir.ts says where they are): served in dev and preview, copied into dist on build.
// The manifest's pack URLs carry a version first (/scenes/<8 hex>/<slug>/…, B-7): locally that segment is dropped.
// three's KTX2Loader brings its Basis transcoder itself (new URL(..., import.meta.url)), so Vite hashes it into assets.
// The API (/v1, its WebSocket, B-1's /__mock controls and the prerecorded voice files) goes to the mock or a local
// backend on ZOUJIN_API (default B-1's port); the Host header passes through so the server's Origin check holds.
import babel from "@rolldown/plugin-babel";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import type { Connect, Plugin, Rollup } from "vite";
import { defineConfig } from "vite";
import { sceneDir } from "./scene-dir.ts";

// the plaza, the castle (F-14), and the road's river (F-10): its two packs, the shared roadside pack and the index that picks a pack by act
const SCENES = [
  "syracuse-square",
  "road-common",
  "road-river-calm",
  "road-river-flood",
  "road-river",
  "castle-throne",
];
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
      const url = req.url?.replace(/^\/scenes\/[0-9a-f]{8}\//, "/scenes/");
      if (!url?.startsWith(prefix)) continue;
      const rel = url.slice(prefix.length);
      const file = resolveUnder(dir, rel);
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

// The service worker (src/sw/worker.ts, F-19) as /sw.js: a chunk of its own, with the files it stores when it installs
// (the shell and the 3D screen, each with what it imports and its CSS) and a build id from every file's name put in
function serviceWorker(): Plugin {
  return {
    name: "zoujin-service-worker",
    apply: "build",
    buildStart() {
      if (process.env.VITEST) return;
      this.emitFile({
        type: "chunk",
        id: path.resolve(import.meta.dirname, "src/sw/worker.ts"),
        fileName: "sw.js",
      });
    },
    generateBundle(_, bundle) {
      const sw = bundle["sw.js"];
      if (sw?.type !== "chunk") return;
      const files = new Set<string>();
      const add = (name: string) => {
        const c = bundle[name];
        if (!c || files.has(name)) return;
        files.add(name);
        if (c.type !== "chunk") return;
        c.imports.forEach(add);
        c.viteMetadata?.importedCss.forEach((f) => files.add(f));
      };
      const start = (c: Rollup.OutputChunk) =>
        (c.isEntry && c !== sw) ||
        !!c.facadeModuleId?.endsWith("/src/screens/WorldScreen.tsx");
      for (const c of Object.values(bundle))
        if (c.type === "chunk" && start(c)) add(c.fileName);
      const build = createHash("sha256")
        .update(Object.keys(bundle).sort().join("\n"))
        .digest("hex")
        .slice(0, 12);
      const list = JSON.stringify(JSON.stringify([...files].sort())).slice(
        1,
        -1,
      );
      sw.code = sw.code
        .replace("__ZOUJIN_PRECACHE__", () => list)
        .replaceAll("__ZOUJIN_BUILD__", build);
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
  plugins: [
    react(),
    babel({ presets: [compiler] }),
    runtimeFiles(),
    serviceWorker(),
  ],
  build: {
    manifest: true,
    target: "es2022",
    rollupOptions: {
      output: {
        // the 3D layer stays one chunk (S-083 ⑤ budgets it as one): the lazy chunks that import from it (the scenes
        // after the plaza, the dev panel, the e2e hook) would otherwise split it into pieces compressed one by one
        // (about 3 KB more brotli). Only the listed modules, not their dependencies (react stays in the shell); the lazy
        // ones stay out (the road's extras and water, the act-end page's prefetch, the ending's staging, the crowd past
        // its presence check, the team's tools in dev/).
        codeSplitting: {
          groups: [
            {
              name: "world",
              includeDependenciesRecursively: false,
              test: (id: string) =>
                /[\\/]node_modules[\\/](three|@react-three[\\/][^\\/]+|suspend-react|its-fine|react-use-measure|zustand[\\/]esm[\\/]traditional|use-sync-external-store)/.test(
                  id,
                )
                  ? !id.includes("libs/basis")
                  : /[\\/]src[\\/]three[\\/]/.test(id) &&
                    !/scene[\\/](extra|land|clouds|prefetch)|[\\/](water|dev)[\\/]|ending[\\/](?!Guard)|crowd[\\/](?!presence)/.test(
                      id,
                    ),
            },
          ],
        },
      },
    },
  },
  server: { host: "127.0.0.1", proxy },
  preview: { host: "127.0.0.1", proxy },
});
