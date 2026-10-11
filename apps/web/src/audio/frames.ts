// The binary frames on the playthrough's socket (api-contract 3.1): byte 0 the kind (0x01 the player's microphone up,
// 0x02 a character's voice down), bytes 1-4 the turnSeq (uint32 big-endian), then mono PCM16 little-endian: 16 kHz
// in 40 ms frames up, 24 kHz in whatever pieces Live sends down.
export const MIC = 0x01;
export const VOICE = 0x02;
export const MIC_RATE = 16_000;
export const VOICE_RATE = 24_000;
export const MIC_FRAME_MS = 40;
export const MIC_FRAME_SAMPLES = (MIC_RATE * MIC_FRAME_MS) / 1000; // 640 samples, 1,280 bytes
const HEAD = 5;

// one microphone frame: the header, then the samples as they are (Int16Array is little-endian on every browser's
// platform; the samples are copied byte for byte)
export function micFrame(turnSeq: number, pcm: Int16Array): ArrayBuffer {
  const out = new Uint8Array(HEAD + pcm.byteLength);
  out[0] = MIC;
  new DataView(out.buffer).setUint32(1, turnSeq >>> 0, false);
  out.set(new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength), HEAD);
  return out.buffer;
}

export type VoiceFrame = { turnSeq: number; samples: Float32Array }; // -1..1 at 24 kHz

// a character's voice frame, or null for anything else (a microphone echo, a short or odd-sized frame)
export function readVoice(buf: ArrayBuffer): VoiceFrame | null {
  if (buf.byteLength < HEAD + 2 || (buf.byteLength - HEAD) % 2) return null;
  const v = new DataView(buf);
  if (v.getUint8(0) !== VOICE) return null;
  const n = (buf.byteLength - HEAD) / 2;
  const samples = new Float32Array(n);
  for (let i = 0; i < n; i++)
    samples[i] = v.getInt16(HEAD + 2 * i, true) / 32768;
  return { turnSeq: v.getUint32(1, false), samples };
}

// server turns have the top bit set (3.1); the client numbers its own from 1 on each connection
export const isServerTurn = (turnSeq: number): boolean => turnSeq >= 0x80000000;
