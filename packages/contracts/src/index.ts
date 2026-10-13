// TypeScript types of the contracts, generated from schemas/ (C-1). The frontend imports them by namespace:
// 契約の TypeScript の型。schemas/ から生成する（C-1）。フロントエンドは名前空間で import する：
//   import type { Api, Data } from "@zoujin/contracts";
// Data is the data contracts (C-2), Api is the API (api-contract); binary holds the WebSocket binary frame constants.
// Data はデータ契約（C-2）、Api は API（api-contract）。binary は WebSocket のバイナリフレームの定数。
export type * as Data from "./generated/data";
export type * as Api from "./generated/api";
export * as binary from "./generated/binary";
