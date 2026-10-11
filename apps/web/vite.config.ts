// Vite for the web front end (frontend-design 3). Besides React, the 3D layer needs a scene's generated files at
// /scenes/<slug>/ and the characters at /cast/ (not in git; scene-dir.ts says where they are): served in dev and preview,
// copied into dist on build.
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
import { castDir, sceneDir } from "./scene-dir.ts";

// the plaza, the castle (F-14), the road (F-10, F-15: its packs, the shared roadside pack and each road scene's index
// that picks a pack by act) and the village (F-11) with the room inside Melos's house (a sub-pack: pack.json, no
// scene.json)
const SCENES = [
  "syracuse-square",
  "road-common",
  "road-river-calm",
  "road-river-flood",
  "road-river",
  "village",
  "village-interior",
  "castle-throne",
  "road-pass-day",
  "road-pass",
  "road-spring-day",
  "road-spring",
  "road-field-day",
  "road-field",
  "road-run-r1",
  "road-run-r2",
  "road-run-r2s",
  "road-run-r3",
  "road-run-night",
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
  const mounts = (): [string, string][] => [
    ...SCENES.map((s): [string, string] => [`/scenes/${s}/`, sceneDir(s)]),
    ["/cast/", castDir()],
  ];
  const serve: Connect.NextHandleFunction = (req, res, next) => {
    for (const [prefix, dir] of mounts()) {
      const url = req.url?.replace(/^\/scenes\/[0-9a-f]{8}\//, "/scenes/");
      if (!url?.startsWith(prefix)) continue;
      const rel = url.slice(prefix.length);
      const file = resolveUnder(dir, rel);
      if (!file) {
        // a 404, not the app's index.html: scene/extra.ts asks for an index.json a single-pack scene does not have
        res.statusCode = 404;
        res.end();
        return;
      }
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
            `${dir} missing: run ${prefix === "/cast/" ? "assets/pipeline/cast" : "assets/pipeline/plaza"}/build.sh (dist has no ${prefix})`,
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
// r3f's Canvas registers every three.js class as a JSX element (extend(THREE) on `import * as THREE`), so nothing of
// three.js can be left out of the build; it registers src/three/catalogue.ts instead, the classes our JSX uses
// (the 3D chunk 249 -> 217 KB brotli). Build only: the dev server's prebundled r3f keeps the whole namespace, and
// catalogue.test.ts keeps the list complete. An r3f that no longer has the line fails the build here.
function threeCatalogue(): Plugin {
  const from = "import * as THREE from 'three';";
  const to = `import * as THREE from ${JSON.stringify(path.resolve(import.meta.dirname, "src/three/catalogue.ts"))};`;
  return {
    name: "zoujin-three-catalogue",
    apply: "build",
    transform(code, id) {
      if (
        !/@react-three[\\/]fiber[\\/]dist[\\/]react-three-fiber\.esm\.js$/.test(
          id,
        )
      )
        return null;
      if (!code.includes(from) || !code.includes("extend(THREE)"))
        this.error(
          `${id}: r3f's Canvas changed, see threeCatalogue in vite.config.ts`,
        );
      return { code: code.replace(from, to), map: null };
    },
  };
}

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
    threeCatalogue(),
  ],
  build: {
    manifest: true,
    target: "es2022",
    rollupOptions: {
      output: {
        // the 3D layer stays one chunk (S-083 ⑤ budgets it as one): the lazy chunks that import from it (the scenes
        // after the plaza, the dev panel, the e2e hook) would otherwise split it into pieces compressed one by one
        // (about 3 KB more brotli). Only the listed modules, not their dependencies (react stays in the shell); the lazy
        // ones stay out (the road's extras, water and run segments, the act-end page's prefetch, the ending's staging, the crowd past
        // its presence check, the realistic characters' bodies, the castle's lamps, the start probe, the team's tools in dev/).
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
                    !/scene[\\/](extra|land|clouds|prefetch)|quality[\\/]probe|[\\/](water|dev|castle|road)[\\/]|cast[\\/]CastBody|ending[\\/](?!Guard)|crowd[\\/](?!presence)/.test(
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
