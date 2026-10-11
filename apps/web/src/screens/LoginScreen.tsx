// Invite code (frontend-design 5, ux-design 3): the code once, then the Cookie. After it, back to where the player was.
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { navigate } from "../app/router";
import { meQuery } from "../app/queries";
import { ApiError, rest } from "../net/rest";
import { copy } from "../ui/copy";

export default function LoginScreen({ next }: { next: string }) {
  const qc = useQueryClient();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!code.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      qc.setQueryData(meQuery.queryKey, await rest.login(code));
      navigate(next, { replace: true });
    } catch (err) {
      const c = err instanceof ApiError ? err.code : "network";
      setError(
        c === "invalid_invite" ? copy["login.wrong"] : copy["login.tooMany"],
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="screen" onSubmit={submit}>
      <h1>{copy["login.title"]}</h1>
      <p>{copy["login.lead"]}</p>
      <input
        className="field"
        aria-label={copy["login.title"]}
        value={code}
        onChange={(e) => setCode(e.target.value)}
        autoComplete="one-time-code"
        autoCapitalize="none"
        spellCheck={false}
      />
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button className="primary" type="submit" disabled={busy || !code.trim()}>
        {copy["login.submit"]}
      </button>
    </form>
  );
}
