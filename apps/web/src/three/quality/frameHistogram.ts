// perf_sample's frame-time histogram (data-design 9.3): 9 fixed bins, bin i counts frames with
// upper(i-1) < interval <= upper(i); the bounds sit just above whole numbers of refreshes (120 Hz 1 and 3, 90 Hz 1,
// 60 Hz 1, 2, 3, 6), so one kind of dropped frame never splits over two bins. Fixed so histograms from different
// front-end versions add up.
export const BIN_UPPER_MS = [8.5, 12, 17, 20, 26, 34, 51, 101] as const;

export function binOf(intervalMs: number): number {
  const i = BIN_UPPER_MS.findIndex((u) => intervalMs <= u);
  return i < 0 ? BIN_UPPER_MS.length : i;
}

export class FrameHistogram {
  private bins = new Array<number>(BIN_UPPER_MS.length + 1).fill(0);

  add(intervalMs: number): void {
    this.bins[binOf(intervalMs)]!++;
  }

  get frames(): number {
    return this.bins.reduce((a, b) => a + b, 0);
  }

  // the counts so far, and start again
  take(): number[] {
    const out = this.bins;
    this.bins = new Array<number>(BIN_UPPER_MS.length + 1).fill(0);
    return out;
  }
}
