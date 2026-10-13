// The private runner is provisioned with the already reviewed cast and the pinned
// CC0 animation source. Verify every input before staging it into this job.
import crypto from "node:crypto";
import console from "node:console";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const [, , source, destination] = process.argv;
if (!source || !destination) {
  throw new Error(
    "usage: stage_web_assets.mjs <private-input-dir> <job-output-dir>",
  );
}
const repo = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const manifest = JSON.parse(
  fs.readFileSync(path.join(repo, "assets/cast/cast.json"), "utf8"),
);
const spec = JSON.parse(
  fs.readFileSync(
    path.join(repo, "assets/pipeline/cast/characters.json"),
    "utf8",
  ),
);
const names = Object.entries(spec.characters).flatMap(([name, value]) => [
  name,
  ...Object.keys(value.variants ?? {}),
]);
if (
  JSON.stringify(names.sort()) !==
  JSON.stringify(Object.keys(manifest.characters).sort())
) {
  throw new Error(
    "cast manifest does not contain exactly the authored characters and variants",
  );
}
const entries = [];
for (const name of names) {
  if (!/^[a-z0-9-]+$/.test(name)) throw new Error("invalid cast name");
  for (const tier of ["walk", "talk_std", "talk_high", "anims"]) {
    const rel = `cast/${name}/${tier}.glb`;
    const expected = manifest.characters[name].files[tier];
    const bytes = fs.readFileSync(path.join(source, rel));
    const sha = crypto.createHash("sha256").update(bytes).digest("hex");
    if (
      !expected ||
      bytes.length !== expected.bytes ||
      sha !== expected.sha256
    ) {
      throw new Error(
        `private CI input differs from the reviewed manifest: ${rel}`,
      );
    }
    entries.push([rel, bytes]);
  }
}
const crowdBuild = fs.readFileSync(
  path.join(repo, "assets/pipeline/crowd/build.sh"),
  "utf8",
);
const pinned = crowdBuild.match(/^UAL_SHA256=([a-f0-9]{64})/m)?.[1];
const motionName = "UAL1_Standard.glb";
const motions = fs.readFileSync(path.join(source, motionName));
if (
  !pinned ||
  crypto.createHash("sha256").update(motions).digest("hex") !== pinned
) {
  throw new Error(
    "private CI animation input is not the pipeline's pinned UAL source",
  );
}
entries.push([motionName, motions]);
// The destination is a job-owned RUNNER_TEMP directory, never the persistent source.
const output = path.resolve(destination);
const input = path.resolve(source);
if (
  output === input ||
  input.startsWith(output + path.sep) ||
  output.startsWith(input + path.sep)
) {
  throw new Error("CI input and job output must be separate directories");
}
fs.rmSync(output, { recursive: true, force: true });
for (const [rel, bytes] of entries) {
  const file = path.join(output, rel);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, bytes);
}
console.log(
  `Verified and staged ${names.length} characters (${entries.length - 1} GLBs) and pinned crowd animation source`,
);
