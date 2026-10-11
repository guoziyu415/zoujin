// copy-ja's 「<br>」: the string splits into lines shown as text nodes, never inserted as HTML (copy-ja 0)
import { Fragment } from "react";

export const splitBr = (s: string): string[] => s.split("<br>");

export function Lines({ text }: { text: string }) {
  const parts = splitBr(text);
  return (
    <>
      {parts.map((p, i) => (
        <Fragment key={i}>
          {i > 0 && <br />}
          {p}
        </Fragment>
      ))}
    </>
  );
}
