import { describe, expect, it } from "vitest";
import { voiceFrame } from "../voice/fakeAudio";
import {
  isServerTurn,
  MIC,
  MIC_FRAME_SAMPLES,
  micFrame,
  readVoice,
} from "./frames";

describe("binary frames (api-contract 3.1)", () => {
  it("a microphone frame: kind, turnSeq big-endian, then the samples little-endian as they are", () => {
    const pcm = new Int16Array(MIC_FRAME_SAMPLES);
    pcm[0] = 1;
    pcm[1] = -2;
    const f = micFrame(258, pcm);
    expect(f.byteLength).toBe(5 + 1280);
    const v = new DataView(f);
    expect(v.getUint8(0)).toBe(MIC);
    expect([...new Uint8Array(f, 1, 4)]).toEqual([0, 0, 1, 2]);
    expect(v.getInt16(5, true)).toBe(1);
    expect(v.getInt16(7, true)).toBe(-2);
  });

  it("a character's voice frame reads back as its turnSeq and -1..1 samples", () => {
    const f = readVoice(voiceFrame(0x80000001, 10))!;
    expect(f.turnSeq).toBe(0x80000001);
    expect(isServerTurn(f.turnSeq)).toBe(true);
    expect(f.samples).toHaveLength(240);
    expect(f.samples[0]).toBeCloseTo(1000 / 32768, 6);
  });

  it("anything else is not a voice frame: a microphone echo, too short, an odd byte count", () => {
    expect(readVoice(micFrame(1, new Int16Array(4)))).toBeNull();
    expect(readVoice(new ArrayBuffer(5))).toBeNull();
    const odd = new Uint8Array(8);
    odd[0] = 0x02;
    expect(readVoice(odd.buffer)).toBeNull();
    expect(isServerTurn(1)).toBe(false);
  });
});
