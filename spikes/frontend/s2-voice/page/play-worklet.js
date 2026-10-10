// Character voice playback: a ring buffer at the context rate.
// 'flush' empties it at once (local barge-in stop) and reports the audio time it went quiet;
// 'started' reports the audio time the first sample of a reply is output.
class Play extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buf = new Float32Array(sampleRate * 30); this.r = 0; this.w = 0;
    this.playing = false; this.prebuffer = Math.round(sampleRate * 0.04); this.tag = 0;
    this.port.onmessage = (e) => {
      const m = e.data;
      if (m.pcm) {
        const a = new Float32Array(m.pcm);
        for (let i = 0; i < a.length; i++) { this.buf[this.w] = a[i]; this.w = (this.w + 1) % this.buf.length; }
        this.tag = m.tag;
      } else if (m.flush) {
        this.r = this.w; const was = this.playing; this.playing = false;
        this.port.postMessage({ flushed: true, t: currentTime, was, id: m.id });
      } else if (m.prebufferMs != null) {
        this.prebuffer = Math.round(sampleRate * m.prebufferMs / 1000);
      }
    };
  }
  avail() { return (this.w - this.r + this.buf.length) % this.buf.length; }
  process(_, outputs) {
    const out = outputs[0][0];
    if (!this.playing && this.avail() >= Math.max(1, this.prebuffer)) {
      this.playing = true;
      this.port.postMessage({ started: true, t: currentTime, tag: this.tag });
    }
    if (this.playing) {
      for (let i = 0; i < out.length; i++) {
        if (this.r === this.w) { out.fill(0, i); this.playing = false; this.port.postMessage({ drained: true, t: currentTime, tag: this.tag }); break; }
        out[i] = this.buf[this.r]; this.r = (this.r + 1) % this.buf.length;
      }
    }
    for (let c = 1; c < outputs[0].length; c++) outputs[0][c].set(out);
    return true;
  }
}
registerProcessor('play', Play);
