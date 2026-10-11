// Microphone → 16 kHz mono PCM16 in 40 ms frames (api-contract 3.1), with the frame's peak for the talk key's ring.
// Posts only while the main thread says the player is holding the key (nothing leaves the worklet otherwise). The
// box filter averages the input samples that fall into each output sample: enough for speech at 44.1 or 48 kHz, and
// what the S2 test page ran on the iPhone.
import type { Scope } from "./scope.ts";

const g = globalThis as unknown as Scope;
const FRAME = 640;

class Capture extends g.AudioWorkletProcessor {
  private ratio = g.sampleRate / 16000;
  private pos = 0; // input samples left before the next output sample
  private acc = 0;
  private n = 0;
  private out = new Int16Array(FRAME);
  private k = 0;
  private peak = 0;
  private on = false;

  constructor() {
    super();
    this.port.onmessage = (e: MessageEvent<{ on: boolean }>) => {
      this.on = e.data.on;
      // a new hold starts a fresh frame
      this.pos = this.acc = this.n = this.k = this.peak = 0;
    };
  }

  process(inputs: Float32Array[][]): boolean {
    const ch = inputs[0]?.[0];
    if (!ch || !this.on) return true;
    for (let i = 0; i < ch.length; i++) {
      const v = ch[i]!;
      this.acc += v;
      this.n++;
      const a = v < 0 ? -v : v;
      if (a > this.peak) this.peak = a;
      this.pos -= 1;
      if (this.pos > 0) continue;
      const s = this.acc / this.n;
      this.out[this.k++] =
        s >= 1 ? 32767 : s <= -1 ? -32768 : Math.round(s * 32767);
      this.acc = this.n = 0;
      this.pos += this.ratio;
      if (this.k === FRAME) {
        this.port.postMessage({ pcm: this.out, peak: this.peak }, [
          this.out.buffer,
        ]);
        this.out = new Int16Array(FRAME);
        this.k = 0;
        this.peak = 0;
      }
    }
    return true;
  }
}

g.registerProcessor("zj-capture", Capture);
