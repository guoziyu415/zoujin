// Microphone -> 16 kHz mono PCM16, posted in 20 ms chunks (320 samples).
// Box-filter resampler: good enough for speech and works for 44.1 / 48 kHz contexts alike.
class Capture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.pos = 0;            // position of the next output sample, in input samples
    this.acc = 0; this.n = 0;
    this.out = new Int16Array(320); this.k = 0;
    this.peak = 0;
  }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      const v = ch[i];
      this.acc += v; this.n++;
      const a = v < 0 ? -v : v; if (a > this.peak) this.peak = a;
      this.pos -= 1;
      if (this.pos <= 0) {
        const s = this.acc / this.n;
        this.out[this.k++] = s >= 1 ? 32767 : s <= -1 ? -32768 : Math.round(s * 32767);
        this.acc = 0; this.n = 0; this.pos += this.ratio;
        if (this.k === 320) {
          this.port.postMessage({ pcm: this.out.buffer, t: currentTime, peak: this.peak }, [this.out.buffer]);
          this.out = new Int16Array(320); this.k = 0; this.peak = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor('capture', Capture);
