# Generated file, do not edit by hand: change packages/contracts/schemas/ and run `uv run contracts-gen`.
# 生成ファイル。手で編集しないこと：packages/contracts/schemas/ を変更して `uv run contracts-gen` を実行する。
"""WebSocket binary frame (api-contract 3.1): byte 0 type, bytes 1–4 turnSeq (uint32 big-endian), then PCM16 little-endian mono / WebSocket のバイナリフレーム（api-contract 3.1）：バイト 0 が種別、バイト 1–4 が turnSeq（uint32 ビッグエンディアン）、その後に PCM16 リトルエンディアンのモノラル"""

HEADER_BYTES = 5
MIC_UP = 1
MIC_UP_SAMPLE_RATE_HZ = 16000
MIC_UP_FRAME_MS = 40
MIC_UP_FRAME_BYTES = 1280
CHARACTER_DOWN = 2
CHARACTER_DOWN_SAMPLE_RATE_HZ = 24000
CLIENT_TURN_SEQ_MAX = 2147483647
SERVER_TURN_SEQ_MIN = 2147483649
