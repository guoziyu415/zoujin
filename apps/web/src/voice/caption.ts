// A character's line on screen follows the voice (frontend-design 7.5, ux-design 7.7): nothing ahead of what has been
// heard. Pure bookkeeping, fed with the playback position (milliseconds of this turn's voice queued and heard):
// - live: each partial transcript (the text so far, api-contract 3.3) shows once the voice queued before it arrived
//   has been heard; the final one the same way, so a final that comes while the voice still plays waits for its end;
// - script (fixed lines, prerecorded lines): split at 、 and 。, segment k shows once the first k segments' share of
//   the characters has been heard; until the length is known it is the longer of what has arrived and 6 characters
//   a second;
// - fallback: the whole line at once (the voice is over by then).
export type Source = "live" | "script" | "fallback";

const CHARS_PER_SECOND = 6;

const CLOSING = /[」』）)]/;

export function segments(text: string): string[] {
  const out: string[] = [];
  let cur = "";
  for (const ch of text) {
    // a closing mark right after 、 or 。 stays with that segment (」 shouldn't start one)
    if (!cur && out.length && CLOSING.test(ch)) {
      out[out.length - 1] += ch;
      continue;
    }
    cur += ch;
    if (ch === "、" || ch === "。") {
      out.push(cur);
      cur = "";
    }
  }
  if (cur) out.push(cur);
  return out;
}

export class Caption {
  private due: { text: string; at: number }[] = []; // live: text to show once `at` ms have been heard
  private script: {
    text: string;
    parts: string[];
    lengthMs: number | null;
  } | null = null;
  shown = "";
  final = false;
  source: Source | null = null;

  // a live piece of text (the text so far) when `queuedMs` of this turn's voice had arrived
  partial(text: string, queuedMs: number): void {
    if (this.final) return;
    this.due.push({ text, at: queuedMs });
  }

  // the one final line of the turn; text null: the transcript failed (shown as such by the subtitles)
  finish(text: string | null, source: Source, queuedMs: number): void {
    this.final = true;
    this.source = source;
    if (text === null) {
      this.due = [];
      return;
    }
    if (source === "fallback") {
      this.due = [];
      this.shown = text;
    } else if (source === "script") {
      this.due = [];
      this.script = { text, parts: segments(text), lengthMs: null };
    } else this.due.push({ text, at: queuedMs });
  }

  // a fixed line whose voice length is known (a prerecorded clip: durationMs from the manifest)
  scripted(text: string, lengthMs: number): void {
    this.final = true;
    this.source = "script";
    this.script = { text, parts: segments(text), lengthMs };
  }

  // the voice is all here (turn_complete): a script line's length is what arrived
  complete(queuedMs: number): void {
    if (this.script && this.script.lengthMs === null)
      this.script.lengthMs = queuedMs;
  }

  // what to show when `heardMs` of the voice has played and `queuedMs` has arrived; true when it changed
  update(heardMs: number, queuedMs: number): boolean {
    const before = this.shown;
    while (this.due.length && this.due[0]!.at <= heardMs)
      this.shown = this.due.shift()!.text;
    const s = this.script;
    if (s) {
      const total = [...s.text].length;
      const length =
        s.lengthMs ?? Math.max(queuedMs, (total / CHARS_PER_SECOND) * 1000);
      let chars = 0;
      let text = "";
      for (const p of s.parts) {
        chars += [...p].length;
        if (heardMs < (chars / total) * length - 1) break;
        text += p;
      }
      this.shown = text;
    }
    return this.shown !== before;
  }

  // the voice has ended (or was cut): whatever is still waiting shows now, unless the line was cut
  flush(): boolean {
    const before = this.shown;
    if (this.due.length) this.shown = this.due[this.due.length - 1]!.text;
    this.due = [];
    if (this.script) this.shown = this.script.text;
    this.script = null;
    return this.shown !== before;
  }

  // a cut (the player spoke over it, a safety pause): stop where it is
  stop(): void {
    this.due = [];
    this.script = null;
  }
}
