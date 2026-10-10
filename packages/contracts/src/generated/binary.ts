// 生成的文件，不要手改：改 packages/contracts/schemas/ 后跑 `uv run contracts-gen`。
// WebSocket 二进制帧（api-contract 3.1）：字节 0 类型，字节 1–4 turnSeq（uint32 大端），之后 PCM16 小端单声道

export const HEADER_BYTES = 5;
export const MIC_UP = 1;
export const MIC_UP_SAMPLE_RATE_HZ = 16000;
export const MIC_UP_FRAME_MS = 40;
export const MIC_UP_FRAME_BYTES = 1280;
export const CHARACTER_DOWN = 2;
export const CHARACTER_DOWN_SAMPLE_RATE_HZ = 24000;
export const CLIENT_TURN_SEQ_MAX = 2147483647;
export const SERVER_TURN_SEQ_MIN = 2147483649;
