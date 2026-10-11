// 「結末を自動で進める」 (ux-design 11.1, 13; S-089): on by default; off, each ending line waits for a tap. Remembered
// on this device; storage that throws (private mode, blocked) just means the default.
import { useSyncExternalStore } from "react";

const KEY = "zj.endAuto";
const subs = new Set<() => void>();

function read(): boolean {
  try {
    return localStorage.getItem(KEY) !== "0";
  } catch {
    return true;
  }
}

let auto = typeof localStorage === "undefined" ? true : read();

export const endingSettings = {
  get auto(): boolean {
    return auto;
  },
  setAuto(on: boolean): void {
    auto = on;
    try {
      localStorage.setItem(KEY, on ? "1" : "0");
    } catch {
      // not remembered; this page still uses it
    }
    for (const f of subs) f();
  },
};

export const useEndingAuto = (): boolean =>
  useSyncExternalStore(
    (f) => {
      subs.add(f);
      return () => subs.delete(f);
    },
    () => auto,
  );
