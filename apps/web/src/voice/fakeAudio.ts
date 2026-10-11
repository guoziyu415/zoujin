// Test helpers for the voice (unit tests only; nothing in the app imports this): an AudioPort that keeps a log of
// what the controller asked for and lets the test play the audio engine's side (a turn becoming audible, playing on,
// running dry), and the character's voice frames as the server sends them.
import type { AudioEvents, AudioPort, Clip, MicResult } from "../audio/engine";
import { VOICE, VOICE_RATE } from "../audio/frames";

const PER_MS = VOICE_RATE / 1000;

export class FakeAudio implements AudioPort {
  log: string[] = [];
  running = true;
  mic = false;
  sending = false;
  micResult: MicResult = { ok: true };
  loadClips = true; // preload makes clips playable
  lastFlushMs: number | null = null;
  private ev: AudioEvents | null = null;
  private queued = new Map<number, number>(); // tag → ms arrived
  private heard = new Map<number, number>(); // tag → ms played
  private loaded = new Set<string>();
  private tag = -1; // the turn whose voice is in the buffer
  private isPlaying = false;

  bind(events: AudioEvents): void {
    this.ev = events;
  }
  unlock(): void {
    this.log.push("unlock");
    this.running = true;
  }
  micOpen(): boolean {
    return this.mic;
  }
  openMic(): Promise<MicResult> {
    this.log.push("openMic");
    if (this.micResult.ok) this.mic = true;
    return Promise.resolve(this.micResult);
  }
  setSending(on: boolean): void {
    if (on !== this.sending) this.log.push(`sending:${on}`);
    this.sending = on;
  }
  releaseMic(): void {
    if (this.mic) this.log.push("releaseMic");
    this.mic = false;
    this.sending = false;
  }
  startTurn(tag: number): void {
    this.queued.set(tag, 0);
    this.heard.set(tag, 0);
  }
  play(tag: number, samples: Float32Array): void {
    this.queued.set(tag, this.queuedMs(tag) + samples.length / PER_MS);
    this.tag = tag;
    this.isPlaying = true;
  }
  flush(): number {
    this.log.push("flush");
    if (this.tag >= 0) this.heard.set(this.tag, this.queuedMs(this.tag));
    this.isPlaying = false;
    return performance.now();
  }
  fadeOut(ms: number): void {
    this.log.push(`fadeOut:${ms}`);
    this.isPlaying = false;
  }
  queuedMs(tag: number): number {
    return this.queued.get(tag) ?? 0;
  }
  heardMs(tag: number): number {
    return this.heard.get(tag) ?? 0;
  }
  playing(): boolean {
    return this.isPlaying;
  }
  preload(clips: Clip[]): void {
    if (this.loadClips) for (const c of clips) this.loaded.add(c.url);
  }
  playClip(clip: Clip, hold?: { tag: number; maxMs: number }): boolean {
    if (!this.loaded.has(clip.url)) return false;
    this.log.push(hold ? `clip:${clip.url}:hold` : `clip:${clip.url}`);
    return true;
  }

  // —— the audio engine's side ——
  audible(tag: number, at = performance.now()): void {
    this.ev!.onStarted(tag, at);
  }
  hear(tag: number, ms: number): void {
    this.heard.set(tag, Math.min(this.queuedMs(tag), this.heardMs(tag) + ms));
    this.ev!.onPosition();
  }
  drain(tag: number): void {
    this.heard.set(tag, this.queuedMs(tag));
    this.isPlaying = false;
    this.ev!.onDrained(tag);
  }
  micFrame(pcm = new Int16Array(640)): void {
    this.ev!.onFrame(pcm);
  }
  interrupt(): void {
    this.ev!.onInterrupted();
  }
}

// a downlink voice frame (api-contract 3.1): kind, turnSeq (uint32 big-endian), ms of 24 kHz PCM16 little-endian
export function voiceFrame(turnSeq: number, ms = 40): ArrayBuffer {
  const n = Math.round(ms * PER_MS);
  const buf = new ArrayBuffer(5 + n * 2);
  const v = new DataView(buf);
  v.setUint8(0, VOICE);
  v.setUint32(1, turnSeq);
  for (let i = 0; i < n; i++) v.setInt16(5 + i * 2, 1000, true);
  return buf;
}
