// What an AudioWorklet module sees (AudioWorkletGlobalScope), typed here instead of as globals so the app's own code
// doesn't see them. Type-only: each worklet reads globalThis through it.
export type Processor = {
  readonly port: MessagePort;
};
export type Scope = {
  sampleRate: number;
  currentTime: number;
  registerProcessor(name: string, ctor: new () => Processor): void;
  AudioWorkletProcessor: new () => Processor;
};
