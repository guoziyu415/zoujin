// The audio engine (frontend-design 7.2-7.4): one AudioContext at the device rate, the microphone through the capture
// worklet, the characters' voice through the playback worklet and a voice bus (a GainNode, so a safety pause can fade
// it in 0.2 s), and the prerecorded lines on the same bus. Only the voice controller drives it, through AudioPort, so
// the controller's tests run on a fake. Nothing here keeps or logs what the microphone hears, nor the device's name.
import { VOICE_RATE } from "./frames";
import { Resampler } from "./resample";

export type MicResult =
  | { ok: true }
  | { ok: false; result: "denied" | "unavailable"; reason: string };

export type Clip = { url: string; text: string; durationMs: number };

// a crowd's line (UX on the closing recordings: 「万歳、王様万歳。」, 「メロスだ！」 are one woman's voice, the ground holds
// hundreds): copies under the recording, each a little late, higher or lower, quieter and to one side
export const CROWD_LAYERS = [
  { delay: 0.07, rate: 0.95, gain: 0.55, pan: -0.5 },
  { delay: 0.16, rate: 1.05, gain: 0.5, pan: 0.45 },
  { delay: 0.24, rate: 0.91, gain: 0.4, pan: -0.2 },
  { delay: 0.11, rate: 1.09, gain: 0.35, pan: 0.7 },
];
export const isCrowd = (speaker: string | null | undefined): boolean =>
  speaker === "char.crowd";

export type AudioEvents = {
  onFrame: (pcm: Int16Array) => void; // 40 ms of 16 kHz microphone while sending
  onStarted: (tag: number, at: number) => void; // a turn's first sample is audible (performance.now() time)
  onDrained: (tag: number) => void; // the buffer ran dry while playing
  onPosition: () => void; // queued / heard moved (the subtitles follow it)
  onInterrupted: () => void; // the system took the audio away (a call, Siri; iOS's "interrupted")
};

// what the voice controller needs from the audio side
export interface AudioPort {
  bind(events: AudioEvents): void; // the controller that gets the events (one playthrough at a time)
  readonly running: boolean;
  unlock(): void; // inside a tap: resume, play a moment of silence, playback session (7.4)
  // the microphone
  micOpen(): boolean;
  openMic(): Promise<MicResult>;
  setSending(on: boolean): void; // the track on and frames flowing, or both off
  releaseMic(): void;
  // the characters' voice
  startTurn(tag: number): void; // a turn with this turnSeq begins (turnSeq starts from 1 on each connection)
  play(tag: number, samples: Float32Array): void; // 24 kHz
  flush(): number; // empty the buffer now; returns performance.now() of the call
  fadeOut(ms: number): void; // the voice bus to silence over ms, then empty (12, safety)
  queuedMs(tag: number): number; // of this turn's voice: arrived
  heardMs(tag: number): number; // of this turn's voice: played (or flushed)
  playing(): boolean;
  // prerecorded lines (manifest prerecorded, 7.8)
  preload(clips: Clip[]): void;
  // false when it isn't loaded (yet); with hold, that turn's live voice waits for the clip, at most maxMs; crowd: a
  // crowd's line, the one recorded voice heard as many (CROWD_LAYERS)
  playClip(
    clip: Clip,
    hold?: { tag: number; maxMs: number },
    crowd?: boolean,
  ): boolean;
  // the ending's staging paused (background, a full page): the clip stops where it is and goes on from there
  pauseClip(): void;
  resumeClip(): void;
  lastFlushMs: number | null; // press → silence of the last flush that cut the voice (the 50 ms budget)
}

// for the 3D layer and the talk key's ring, read in their own frame loops (no React updates at 50 Hz)
export const levels = { mouth: 0, mic: 0 };

type Session = { type: string };
const audioSession = (): Session | undefined =>
  (navigator as Navigator & { audioSession?: Session }).audioSession;

function setSessionType(type: "playback" | "play-and-record"): void {
  try {
    const s = audioSession();
    if (s) s.type = type; // iOS 17+ (WebKit's Audio Session API); others don't have it
  } catch {
    // older Safari
  }
}

export class AudioEngine implements AudioPort {
  private ctx: AudioContext | null = null;
  private loading: Promise<void> | null = null;
  private playNode: AudioWorkletNode | null = null;
  private capNode: AudioWorkletNode | null = null;
  private bus: GainNode | null = null;
  private stream: MediaStream | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private resampler: Resampler | null = null;
  private resampleTag = -1;
  private sending = false;
  private queued = 0; // samples (context rate) handed to the playback worklet
  private consumed = 0; // samples that left it
  private turnStart = new Map<number, number>(); // tag → `queued` when its first sample arrived
  private isPlaying = false;
  private clips = new Map<string, AudioBuffer | null>();
  private clipNode: AudioBufferSourceNode | null = null;
  private layerNodes: AudioBufferSourceNode[] = []; // a crowd's line's copies (CROWD_LAYERS)
  // where the clip is (context time)
  private clipAt = {
    buf: null as AudioBuffer | null,
    start: 0,
    offset: 0,
    crowd: false,
  };
  private clipPaused = false;
  private held: Float32Array[] = []; // live voice waiting behind a prerecorded aizuchi
  private holdTag = -1;
  private holdTimer: ReturnType<typeof setTimeout> | undefined;
  private flushAt: number | null = null;
  lastFlushMs: number | null = null;
  private on: AudioEvents = {
    onFrame: () => {},
    onStarted: () => {},
    onDrained: () => {},
    onPosition: () => {},
    onInterrupted: () => {},
  };

  constructor(private readonly worklets: { capture: string; play: string }) {}

  bind(events: AudioEvents): void {
    this.on = events;
  }

  get running(): boolean {
    return this.ctx?.state === "running";
  }

  unlock(): void {
    const ctx = this.context();
    void ctx.resume().catch(() => {});
    // a moment of silence inside the tap keeps iOS from muting later sound
    const b = ctx.createBuffer(1, 1, ctx.sampleRate);
    const s = ctx.createBufferSource();
    s.buffer = b;
    s.connect(ctx.destination);
    s.start();
    if (!this.stream) setSessionType("playback");
    void this.load();
  }

  // back on the page (frontend-design 9.5): false when the sound needs a tap to come back. A context that never
  // started or still runs needs nothing (a desktop tab switch); one the browser lets resume without a gesture
  // comes back here on its own.
  async resumeQuietly(): Promise<boolean> {
    const ctx = this.ctx;
    if (!ctx || this.running) return true;
    await Promise.race([
      ctx.resume().catch(() => {}),
      new Promise((r) => setTimeout(r, 300)),
    ]);
    return this.running;
  }

  private context(): AudioContext {
    if (this.ctx) return this.ctx;
    const ctx = new AudioContext({ latencyHint: "interactive" });
    ctx.onstatechange = () => {
      if ((ctx.state as string) === "interrupted" || ctx.state === "suspended")
        this.on.onInterrupted();
    };
    this.ctx = ctx;
    return ctx;
  }

  private load(): Promise<void> {
    this.loading ??= (async () => {
      const ctx = this.context();
      await ctx.audioWorklet.addModule(this.worklets.play);
      await ctx.audioWorklet.addModule(this.worklets.capture);
      const bus = ctx.createGain();
      bus.connect(ctx.destination);
      const play = new AudioWorkletNode(ctx, "zj-play", {
        numberOfInputs: 0,
        outputChannelCount: [2],
      });
      play.connect(bus);
      play.port.onmessage = (e: MessageEvent<PlayOut>) => this.fromPlay(e.data);
      const cap = new AudioWorkletNode(ctx, "zj-capture", {
        numberOfInputs: 1,
        numberOfOutputs: 1,
        outputChannelCount: [1],
      });
      // a silent sink keeps the capture node pulled
      const sink = ctx.createGain();
      sink.gain.value = 0;
      cap.connect(sink).connect(ctx.destination);
      cap.port.onmessage = (
        e: MessageEvent<{ pcm: Int16Array; peak: number }>,
      ) => {
        levels.mic = e.data.peak;
        if (this.sending) this.on.onFrame(e.data.pcm);
      };
      this.bus = bus;
      this.playNode = play;
      this.capNode = cap;
      if (this.source) this.source.connect(cap);
    })();
    return this.loading;
  }

  // —— the microphone ——

  micOpen(): boolean {
    return !!this.stream?.getAudioTracks().some((t) => t.readyState === "live");
  }

  async openMic(): Promise<MicResult> {
    if (this.micOpen()) return { ok: true };
    if (!navigator.mediaDevices?.getUserMedia)
      return { ok: false, result: "unavailable", reason: "no_api" };
    const ctx = this.context();
    setSessionType("play-and-record");
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
      });
    } catch (err) {
      setSessionType("playback");
      return micError(err, await permissionState());
    }
    for (const t of this.stream.getAudioTracks()) t.enabled = this.sending;
    this.source = ctx.createMediaStreamSource(this.stream);
    await this.load();
    if (this.capNode) this.source.connect(this.capNode);
    return { ok: true };
  }

  setSending(on: boolean): void {
    this.sending = on;
    for (const t of this.stream?.getAudioTracks() ?? []) t.enabled = on;
    this.capNode?.port.postMessage({ on });
    if (!on) levels.mic = 0;
  }

  releaseMic(): void {
    this.setSending(false);
    try {
      this.source?.disconnect();
    } catch {
      // already
    }
    for (const t of this.stream?.getTracks() ?? []) t.stop();
    this.stream = null;
    this.source = null;
    setSessionType("playback");
  }

  // —— the characters' voice ——

  startTurn(tag: number): void {
    this.turnStart.delete(tag);
    if (tag === this.resampleTag) this.resampler = null;
  }

  play(tag: number, samples: Float32Array): void {
    const ctx = this.ctx;
    if (!ctx || !this.playNode) return;
    if (tag !== this.resampleTag || !this.resampler) {
      this.resampler = new Resampler(VOICE_RATE, ctx.sampleRate);
      this.resampleTag = tag;
    }
    const out = this.resampler.push(samples);
    if (!this.turnStart.has(tag)) {
      this.turnStart.set(tag, this.queued);
      if (this.turnStart.size > 8)
        this.turnStart.delete(this.turnStart.keys().next().value!);
    }
    this.queued += out.length;
    if (this.holdTag === tag) this.held.push(out);
    else this.playNode.port.postMessage({ pcm: out, tag }, [out.buffer]);
    this.on.onPosition();
  }

  flush(): number {
    const at = performance.now();
    this.flushAt = at;
    this.release(false);
    this.stopClip();
    this.playNode?.port.postMessage({ flush: true });
    return at;
  }

  fadeOut(ms: number): void {
    const ctx = this.ctx;
    const bus = this.bus;
    if (!ctx || !bus) return;
    const now = ctx.currentTime;
    bus.gain.cancelScheduledValues(now);
    bus.gain.setValueAtTime(bus.gain.value, now);
    bus.gain.linearRampToValueAtTime(0, now + ms / 1000);
    setTimeout(() => {
      this.release(false);
      this.stopClip();
      this.playNode?.port.postMessage({ flush: true });
      bus.gain.cancelScheduledValues(ctx.currentTime);
      bus.gain.setValueAtTime(1, ctx.currentTime + 0.05); // after the flush has been taken
    }, ms);
  }

  queuedMs(tag: number): number {
    const start = this.turnStart.get(tag);
    return start === undefined ? 0 : this.ms(this.queued - start);
  }

  heardMs(tag: number): number {
    const start = this.turnStart.get(tag);
    return start === undefined
      ? 0
      : this.ms(Math.max(0, this.consumed - start));
  }

  playing(): boolean {
    return this.isPlaying || !!this.clipNode;
  }

  private ms(samples: number): number {
    return this.ctx ? (samples / this.ctx.sampleRate) * 1000 : 0;
  }

  private fromPlay(m: PlayOut): void {
    if ("level" in m) {
      levels.mouth = m.level;
      this.consumed = m.consumed;
      this.on.onPosition();
    } else if ("started" in m) {
      this.isPlaying = true;
      this.on.onStarted(m.tag, this.toPerf(m.t));
    } else if ("drained" in m) {
      this.isPlaying = false;
      this.consumed = m.consumed;
      levels.mouth = 0;
      this.on.onPosition();
      this.on.onDrained(m.tag);
    } else if ("flushed" in m) {
      this.isPlaying = false;
      this.consumed = m.consumed;
      levels.mouth = 0;
      if (m.was && this.flushAt !== null)
        this.lastFlushMs = Math.max(
          0,
          Math.round(this.toPerf(m.t) - this.flushAt),
        );
      this.flushAt = null;
      this.on.onPosition();
    }
  }

  // an audio-clock time to performance.now() time (when it actually comes out of the speaker)
  private toPerf(t: number): number {
    const ctx = this.ctx!;
    const ts = ctx.getOutputTimestamp?.();
    if (ts?.performanceTime && ts.contextTime !== undefined)
      return ts.performanceTime + (t - ts.contextTime) * 1000;
    return (
      performance.now() +
      (t - ctx.currentTime + (ctx.outputLatency || ctx.baseLatency || 0)) * 1000
    );
  }

  // —— prerecorded lines ——

  preload(clips: Clip[]): void {
    const ctx = this.ctx;
    if (!ctx) return;
    for (const c of clips) {
      if (this.clips.has(c.url)) continue;
      this.clips.set(c.url, null);
      fetch(c.url, { credentials: "same-origin" })
        .then((r) =>
          r.ok ? r.arrayBuffer() : Promise.reject(new Error(String(r.status))),
        )
        .then((b) => ctx.decodeAudioData(b))
        .then((buf) => this.clips.set(c.url, buf))
        .catch(() => console.debug("[audio] a prerecorded line didn't load"));
    }
  }

  // plays a loaded clip on the voice bus; the live voice of hold.tag that arrives meanwhile waits for it to end, at
  // most hold.maxMs (7.8: an aizuchi delays the real answer by at most 0.5 s)
  playClip(
    clip: Clip,
    hold?: { tag: number; maxMs: number },
    crowd = false,
  ): boolean {
    const ctx = this.ctx;
    const buf = this.clips.get(clip.url);
    if (!ctx || !buf || !this.bus) return false;
    this.stopClip();
    this.startClip(ctx, buf, 0, crowd);
    if (hold) {
      this.holdTag = hold.tag;
      clearTimeout(this.holdTimer);
      this.holdTimer = setTimeout(() => {
        this.stopClip();
        this.release(true);
      }, hold.maxMs);
    }
    return true;
  }

  private startClip(
    ctx: AudioContext,
    buf: AudioBuffer,
    offset: number,
    crowd: boolean,
  ): void {
    const node = ctx.createBufferSource();
    node.buffer = buf;
    node.connect(this.bus!);
    node.onended = () => {
      if (this.clipNode === node) this.clipNode = null;
      this.release(true);
    };
    node.start(0, offset);
    this.clipNode = node;
    this.clipAt = { buf, start: ctx.currentTime, offset, crowd };
    if (!crowd) return;
    for (const l of CROWD_LAYERS) {
      const copy = ctx.createBufferSource();
      copy.buffer = buf;
      copy.playbackRate.value = l.rate;
      const gain = ctx.createGain();
      gain.gain.value = l.gain;
      copy.connect(gain);
      if (ctx.createStereoPanner) {
        const pan = ctx.createStereoPanner();
        pan.pan.value = l.pan;
        gain.connect(pan).connect(this.bus!);
      } else gain.connect(this.bus!);
      copy.start(ctx.currentTime + l.delay, offset);
      // the slower copies end with the recording, not after it (PM on #156): faded out over its last 0.1 s
      const end = ctx.currentTime + buf.duration - offset;
      gain.gain.setTargetAtTime(0, end - 0.1, 0.03);
      copy.stop(end);
      this.layerNodes.push(copy);
    }
  }

  pauseClip(): void {
    const ctx = this.ctx;
    if (!ctx || !this.clipNode || this.clipPaused) return;
    const { start, offset } = this.clipAt;
    this.clipAt = { ...this.clipAt, offset: offset + ctx.currentTime - start };
    this.stopClip();
    this.clipPaused = true;
  }

  resumeClip(): void {
    const ctx = this.ctx;
    const { buf, offset, crowd } = this.clipAt;
    if (!this.clipPaused) return;
    this.clipPaused = false;
    if (!ctx || !buf || !this.bus || offset >= buf.duration) return;
    this.startClip(ctx, buf, offset, crowd);
  }

  private stopClip(): void {
    this.clipPaused = false; // stopped for good (a flush, a fade, the next clip): nothing to go on with
    for (const copy of this.layerNodes)
      try {
        copy.stop();
      } catch {
        // not started
      }
    this.layerNodes = [];
    const n = this.clipNode;
    this.clipNode = null;
    if (!n) return;
    n.onended = null;
    try {
      n.stop();
    } catch {
      // not started
    }
  }

  // the live voice that waited behind a clip goes to the buffer (or is dropped by a flush)
  private release(send: boolean): void {
    clearTimeout(this.holdTimer);
    const tag = this.holdTag;
    const held = this.held;
    this.holdTag = -1;
    this.held = [];
    if (!send || !this.playNode) return;
    for (const out of held)
      this.playNode.port.postMessage({ pcm: out, tag }, [out.buffer]);
  }
}

type PlayOut =
  | { level: number; consumed: number }
  | { started: true; t: number; tag: number }
  | { drained: true; t: number; tag: number; consumed: number }
  | { flushed: true; t: number; was: boolean; consumed: number };

// NotAllowedError is a "no" from the player or the browser, except when the permission says granted: iOS 26.3-26.6
// throws it after a "yes" once its audio daemon has crashed (WebKit bug 319706), and then a reload or text is the way
// on, which is what the "unavailable" copy says (ux-design 12)
function micError(err: unknown, permission: PermissionState | null): MicResult {
  const name = err instanceof DOMException ? err.name : "Error";
  if (
    (name === "NotAllowedError" || name === "SecurityError") &&
    permission !== "granted"
  )
    return { ok: false, result: "denied", reason: name };
  return { ok: false, result: "unavailable", reason: name };
}

async function permissionState(): Promise<PermissionState | null> {
  try {
    return (
      await navigator.permissions.query({
        name: "microphone" as PermissionName,
      })
    ).state;
  } catch {
    return null; // not supported (older Safari)
  }
}
