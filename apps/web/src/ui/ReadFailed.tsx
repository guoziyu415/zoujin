// Data that didn't come (ux-design 12: every failure has a next step): 「通信できませんでした。」 and a way to try again.
// A 401 isn't this: the client sends the player to the invite page.
import { ApiError } from "../net/rest";
import { copy } from "./copy";

export const readFailed = (q: { isError: boolean; error: unknown }): boolean =>
  q.isError && !(q.error instanceof ApiError && q.error.status === 401);

export function ReadFailed({ onRetry }: { onRetry: () => void }) {
  return (
    <>
      <p className="error" role="alert">
        {copy["net.failed"]}
      </p>
      <button className="secondary" onClick={onRetry}>
        {copy["net.retry"]}
      </button>
    </>
  );
}
