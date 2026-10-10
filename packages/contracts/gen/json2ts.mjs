// 把 codegen 拼好的一个 bundle（只有 $defs）编成 TypeScript，C-1。由 `uv run contracts-gen` 调用，不单独跑。
// 用法：node gen/json2ts.mjs <bundle.json> <out.ts> <头部注释>
import { readFile, writeFile } from "node:fs/promises";
import { compile } from "json-schema-to-typescript";

const [bundlePath, outPath, header] = process.argv.slice(2);
const bundle = JSON.parse(await readFile(bundlePath, "utf8"));
const rootName = bundle.title;

let ts = await compile(bundle, rootName, {
  bannerComment: "",
  unreachableDefinitions: true,
  additionalProperties: false,
  // 长度上下限不变成元组，数组一律 T[]（C-1 前端评审：minItems 也会生成元组，前端从数组拼时报 TS2322）。
  ignoreMinAndMaxItems: true,
  strictIndexSignatures: true,
  unknownAny: true,
  format: true,
  style: { printWidth: 120 },
  $refOptions: { resolve: { file: false, http: false } },
});

// bundle 的根只是个容器，生成的根类型删掉。
const rootDecl = new RegExp(
  `^export (?:interface ${rootName} \\{[^]*?^\\}|type ${rootName} = [^;]*;)\\n`,
  "m",
);
if (!rootDecl.test(ts)) throw new Error(`没找到根类型 ${rootName}`);
ts = ts.replace(rootDecl, "");
// 去掉生成器给每个 $defs 条目加的「referenced by …」注释，只留 Schema 里的说明。
ts = ts
  .replace(
    /^ \* This interface was referenced by `\w+`'s JSON-Schema\n \* via the `definition` "\w+"\.\n/gm,
    "",
  )
  .replace(/^ \*\n(?= \*\/)/gm, "")
  .replace(/^\/\*\*\n \*\/\n/gm, "");
await writeFile(outPath, `${header}\n${ts.trimStart()}`);
