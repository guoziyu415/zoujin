// The TypeScript part of the contract tests (C-1): the generated types work under strict, narrow by type, and reject extra fields.
// 契約テストの TypeScript 部分（C-1）：生成された型が strict で使え、type で絞り込め、余分なフィールドはエラーになる。
// Type-checked only (pnpm typecheck), never run.
// 型チェック（pnpm typecheck）のみで、実行はしない。
import type { Api, Data } from "../src/index";
import { binary } from "../src/index";

export const hello: Api.ClientMessage = {
  type: "hello",
  lastSeq: 0,
  clientVersion: "web-0.0.0",
};

export function describe(message: Api.ServerMessage): string {
  switch (message.type) {
    case "commit":
      return `${message.fromSeq}-${message.seq}:${message.events.map((e) => e.eventId).join(",")}`;
    case "transcript":
      return message.text ?? "";
    case "act_ended":
      return message.options
        .map((o) => o.enRoute?.choices.map((c) => c.label).join("/") ?? o.label)
        .join(",");
    case "error":
      return message.error.code;
    default:
      return message.type;
  }
}

export function eventIds(response: Api.EventsResponse): Data.EventId[] {
  return response.events.map((e) => e.eventId);
}

export const frameBytes: number = binary.MIC_UP_FRAME_BYTES;

export const extra: Api.NearMessage = {
  type: "near",
  character: "char.melos",
  // @ts-expect-error extra field: the Schema is closed, so the generated type rejects it / 余分なフィールド：Schema が閉じているので生成された型は許さない
  distance: 3,
};

export const typo: Api.ClientMessage = {
  // @ts-expect-error misspelled type / type の綴り間違い
  type: "nearby",
  character: "char.melos",
};

// A fixed-length tuple (prefixItems) is generated as [number, string], not never[]
// 固定長のタプル（prefixItems）は never[] ではなく [number, string] として生成される
export const bands: Data.Clock["labels"]["bands"] = [
  [0, "未明"],
  [1140, "日没"],
];
