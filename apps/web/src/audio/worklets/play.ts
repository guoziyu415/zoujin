// The characters' voice: a ring buffer at the context rate (frontend-design 7.3). Starts once a little has gathered
// (prebuffer, against network jitter), and reports:
// - started / drained: the audio time a turn's first sample went out, and when the buffer ran dry while playing;
// - flushed: emptied at once (the player spoke over the character, frontend-design 7.3), with the audio time;
// - level every ~20 ms while playing: the output's loudness (the mouth, 7.3) and how many samples have left the
//   buffer (played or flushed), which the subtitles follow (7.5).
import type { Scope } from "./scope.ts";

const g = globalThis as unknown as Scope;

type In =
  | { pcm: Float32Array; tag: number }
  | { flush: true }
  | { prebufferMs: number };

class Play extends g.AudioWorkletProcessor {
  private buf = new Float32Array(g.sampleRate * 60);
  private r = 0;
  private w = 0;
  private playing = false;
  private prebuffer = Math.round(g.sampleRate * 0.08);
  private tag = 0;
  private consumed = 0; // samples that left the buffer since the start
  private sq = 0; // sum of squares since the last level report
  private since = 0;
  private quiet = true; // the last level report was silence (reports stop until there is sound again)
  private readonly every = Math.round(g.sampleRate * 0.02);

  constructor() {
    super();
    this.port.onmessage = (e: MessageEvent<In>) => {
      const m = e.data;
      if ("pcm" in m) {
        const a = m.pcm;
        for (let i = 0; i < a.length; i++) {
          this.buf[this.w] = a[i]!;
          this.w = (this.w + 1) % this.buf.length;
        }
        this.tag = m.tag;
      } else if ("flush" in m) {
        const was = this.playing;
        this.consumed += this.avail();
        this.r = this.w;
        this.playing = false;
        this.port.postMessage({
          flushed: true,
          t: g.currentTime,
          was,
          consumed: this.consumed,
        });
      } else this.prebuffer = Math.round((g.sampleRate * m.prebufferMs) / 1000);
    };
  }

  private avail(): number {
    return (this.w - this.r + this.buf.length) % this.buf.length;
  }

  process(_: Float32Array[][], outputs: Float32Array[][]): boolean {
    const out = outputs[0]![0]!;
    if (!this.playing && this.avail() >= Math.max(1, this.prebuffer)) {
      this.playing = true;
      this.port.postMessage({ started: true, t: g.currentTime, tag: this.tag });
    }
    let i = 0;
    if (this.playing) {
      for (; i < out.length; i++) {
        if (this.r === this.w) {
          this.playing = false;
          this.port.postMessage({
            drained: true,
            t: g.currentTime,
            tag: this.tag,
            consumed: this.consumed,
          });
          break;
        }
        const v = this.buf[this.r]!;
        out[i] = v;
        this.sq += v * v;
        this.r = (this.r + 1) % this.buf.length;
        this.consumed++;
      }
    }
    out.fill(0, i);
    for (let c = 1; c < outputs[0]!.length; c++) outputs[0]![c]!.set(out);
    this.since += out.length;
    if (this.since >= this.every) {
      const level = Math.sqrt(this.sq / this.since);
      if (this.playing || level > 0 || !this.quiet)
        this.port.postMessage({ level, consumed: this.consumed });
      this.quiet = level === 0;
      this.sq = 0;
      this.since = 0;
    }
    return true;
  }
}

g.registerProcessor("zj-play", Play);
