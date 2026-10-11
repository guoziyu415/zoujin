// The characters' 24 kHz voice to the AudioContext's rate (frontend-design 7.3: one context at the device rate, so
// the conversion is ours). Linear interpolation that carries its position and last sample across the pieces of one
// turn, so the joins between network pieces don't click. A new turn starts from reset().
export class Resampler {
  private pos = 0; // where the next output sample falls, in input samples, counted from the previous piece's last one
  private last = 0; // the previous piece's last sample (input index -1 of the next piece)
  private readonly step: number;

  constructor(
    from: number,
    readonly to: number,
  ) {
    this.step = from / to;
  }

  reset(): void {
    this.pos = 0;
    this.last = 0;
  }

  push(input: Float32Array): Float32Array {
    if (this.step === 1) return input;
    const out: number[] = [];
    // positions are relative to the previous piece's last sample: x = 0 is `last`, x = k is input[k - 1]
    let x = this.pos;
    const at = (k: number) => (k === 0 ? this.last : input[k - 1]!);
    while (x <= input.length) {
      const k = Math.floor(x);
      const f = x - k;
      const a = at(k);
      out.push(f === 0 || k >= input.length ? a : a + (at(k + 1) - a) * f);
      x += this.step;
    }
    this.pos = x - input.length;
    if (input.length) this.last = input[input.length - 1]!;
    return Float32Array.from(out);
  }
}
