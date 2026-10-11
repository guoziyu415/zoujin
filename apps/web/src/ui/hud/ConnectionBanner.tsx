// The connection as the player sees it (ux-design 12, api-contract 4): a quiet 「つながり直しています」 while the socket
// retries, the full message with 「もう一度つなぐ」 after 15 s, and 4009's 「この画面で続ける」.
import { useEffect, useState } from "react";
import { play } from "../../net/play";
import { useUi } from "../../stores/ui";
import { copy } from "../copy";

export const ESCALATE_MS = 15_000;

export function ConnectionBanner() {
  const connection = useUi((s) => s.connection);
  const downSince = useUi((s) => s.downSince);
  const [long, setLong] = useState(false);
  useEffect(() => {
    setLong(false);
    if (downSince === null) return;
    const id = setTimeout(
      () => setLong(true),
      Math.max(0, downSince + ESCALATE_MS - performance.now()),
    );
    return () => clearTimeout(id);
  }, [downSince]);

  if (connection === "taken")
    return (
      <div className="banner" role="alert">
        <span>{copy["tab.taken"]}</span>
        <button onClick={play.reconnect}>{copy["tab.takeBack"]}</button>
      </div>
    );
  if (connection !== "reconnecting") return null;
  return long ? (
    <div className="banner" role="alert">
      <span>{copy["net.lost"]}</span>
      <button onClick={play.reconnect}>{copy["net.retry"]}</button>
    </div>
  ) : (
    <div className="banner" role="status">
      <span>{copy["net.reconnecting"]}</span>
    </div>
  );
}
