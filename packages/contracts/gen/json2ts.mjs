// Compile one bundle (only $defs) assembled by codegen into TypeScript, C-1. Called by `uv run contracts-gen`, not run on its own.
// codegen がまとめた bundle 1 つ（$defs のみ）を TypeScript にコンパイルする（C-1）。`uv run contracts-gen` から呼ばれ、単独では実行しない。
// Usage: node gen/json2ts.mjs <bundle.json> <out.ts> <header comment>
// 使い方：node gen/json2ts.mjs <bundle.json> <out.ts> <ヘッダーコメント>
import { readFile, writeFile } from "node:fs/promises";
import { compile } from "json-schema-to-typescript";

const [bundlePath, outPath, header] = process.argv.slice(2);
const bundle = JSON.parse(await readFile(bundlePath, "utf8"));
const rootName = bundle.title;

let ts = await compile(bundle, rootName, {
  bannerComment: "",
  unreachableDefinitions: true,
  additionalProperties: false,
  // Length bounds do not become tuples; arrays are always T[] (C-1 frontend review: minItems also produced tuples, and building them from arrays in the frontend raised TS2322).
  // 長さの上下限をタプルにせず、配列は常に T[] とする（C-1 フロントエンドレビュー：minItems でもタプルが生成され、フロントエンドで配列から組み立てると TS2322 になった）。
  ignoreMinAndMaxItems: true,
  strictIndexSignatures: true,
  unknownAny: true,
  format: true,
  style: { printWidth: 120 },
  $refOptions: { resolve: { file: false, http: false } },
});

// The bundle's root is only a container, so delete the generated root type.
// bundle のルートは入れ物にすぎないので、生成されたルートの型を削除する。
const rootDecl = new RegExp(
  `^export (?:interface ${rootName} \\{[^]*?^\\}|type ${rootName} = [^;]*;)\\n`,
  "m",
);
if (!rootDecl.test(ts))
  throw new Error(
    `Root type ${rootName} not found / ルートの型 ${rootName} が見つからない`,
  );
ts = ts.replace(rootDecl, "");
// Remove the "referenced by …" comments the generator adds to each $defs entry, keeping only the Schema's descriptions.
// 生成器が各 $defs 項目に付ける「referenced by …」のコメントを取り除き、Schema の説明だけを残す。
ts = ts
  .replace(
    /^ \* This interface was referenced by `\w+`'s JSON-Schema\n \* via the `definition` "\w+"\.\n/gm,
    "",
  )
  .replace(/^ \*\n(?= \*\/)/gm, "")
  .replace(/^\/\*\*\n \*\/\n/gm, "");
await writeFile(outPath, `${header}\n${ts.trimStart()}`);
