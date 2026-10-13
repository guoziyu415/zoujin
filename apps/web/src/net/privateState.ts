// Invite-code account boundary: the story, screen and pending handover snapshot held in memory must not be left for the next account.
// 招待コードのアカウント境界：メモリ上のストーリー、画面、引き継ぎ待ちのスナップショットを次のアカウントに残してはならない。
import { clearSnapshots } from "../app/queries";
import { endingFrame, resetStory } from "../stores/story";
import { setWorld } from "../stores/world";
import { clearTelemetry } from "../telemetry/telemetry";
import { closePlay } from "./play";

export function clearPrivateState(): void {
  closePlay();
  clearTelemetry();
  clearSnapshots();
  resetStory();
  endingFrame.set(null);
  setWorld(null);
  try {
    for (const key of Object.keys(sessionStorage)) {
      if (key.startsWith("zoujin.role.")) sessionStorage.removeItem(key);
    }
  } catch {
    /* storage can be disabled; all current data lives in the server library */
  }
}
