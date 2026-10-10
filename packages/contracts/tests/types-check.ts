// 契约测试的 TypeScript 部分（C-1）：生成的类型在 strict 下能用，按 type 收窄，多余字段报错。
// 只做类型检查（pnpm typecheck），不运行。
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
  // @ts-expect-error 多余的字段：Schema 关死了，生成的类型不允许
  distance: 3,
};

export const typo: Api.ClientMessage = {
  // @ts-expect-error type 拼错
  type: "nearby",
  character: "char.melos",
};

// 定长元组（prefixItems）生成 [number, string]，不是 never[]
export const bands: Data.Clock["labels"]["bands"] = [
  [0, "未明"],
  [1140, "日没"],
];
