// 邀请码账号边界：内存中的剧情、画面、待交接快照不能留给下一个账号。
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
