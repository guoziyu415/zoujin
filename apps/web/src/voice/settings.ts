// The player's voice settings, kept on this device (a convenience; anything stored can be missing or throw):
// - micMode (S-073 ③, a switch until F-3's measurements pick the default): "session" takes the microphone when a
//   conversation starts and mutes it between turns; "perTurn" takes and releases it on each press;
// - tap (ux-design 7.1 タップで話す): tap to start, tap again to send, for players who can't hold the key;
// - text: the player chose 文字で話す in the primer; the keyboard key stays until they go back to voice.
const KEY = "zj.voice";

type Stored = {
  micMode?: "session" | "perTurn";
  tap?: boolean;
  text?: boolean;
};

function read(): Stored {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}") as Stored;
  } catch {
    return {};
  }
}

function write(patch: Stored): void {
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...read(), ...patch }));
  } catch {
    // private mode, blocked storage: the setting lasts for this page
  }
}

const stored = typeof localStorage === "undefined" ? {} : read();

export const voiceSettings = {
  micMode: stored.micMode ?? ("session" as "session" | "perTurn"),
  tap: stored.tap ?? false,
  text: stored.text ?? false,
  set(patch: { micMode?: "session" | "perTurn"; tap?: boolean }): void {
    Object.assign(this, patch);
    write(patch);
  },
  rememberText(on: boolean): void {
    if (this.text === on) return;
    this.text = on;
    write({ text: on });
  },
};
