// 契约的 TypeScript 类型，从 schemas/ 生成（C-1）。前端按命名空间导入：
//   import type { Api, Data } from "@zoujin/contracts";
// Data 是数据契约（C-2），Api 是接口（api-contract）；binary 是 WebSocket 二进制帧的常量。
export type * as Data from "./generated/data";
export type * as Api from "./generated/api";
export * as binary from "./generated/binary";
