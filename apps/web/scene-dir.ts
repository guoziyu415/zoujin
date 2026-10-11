// Where a scene's generated files are (assets/pipeline/plaza/build.sh writes them; they are not in git, README there).
// Default assets/scenes/<slug>/build; ZOUJIN_SCENE_ROOT=<dir> uses <dir>/<slug> instead (CI builds into the runner's temp).
import path from "node:path";
import { fileURLToPath } from "node:url";

const repo = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);

export function sceneDir(slug: string): string {
  const root = process.env.ZOUJIN_SCENE_ROOT;
  return root
    ? path.resolve(root, slug)
    : path.join(repo, "assets/scenes", slug, "build");
}

// The characters' files (assets/pipeline/cast/build.sh, F-16; not in git): default assets/cast/build, or
// ZOUJIN_CAST_ROOT=<dir>.
export function castDir(): string {
  const root = process.env.ZOUJIN_CAST_ROOT;
  return root ? path.resolve(root) : path.join(repo, "assets/cast/build");
}
