// The helplines (ux-design 14.3), shared by the safety card and the panel: name, how and when, one button each.
// The phone number is also text, selectable and unbroken (some in-app browsers do nothing on tel:). Web pages open
// in a new tab so the story page stays.
import { copy, helplines } from "../copy";

export function Helplines() {
  return (
    <ul className="helplines" aria-label={copy["safety.pause.list"]}>
      {helplines.map((h) => (
        <li key={h.name}>
          <strong>{h.name}</strong>
          <span className="how">
            {h.how}
            {"number" in h && (
              <>
                {" "}
                <span className="tel">{h.number}</span>
              </>
            )}
          </span>
          <a
            className="button"
            href={h.href}
            {...(h.href.startsWith("tel:")
              ? {}
              : { target: "_blank", rel: "noopener noreferrer" })}
          >
            {h.button}
          </a>
        </li>
      ))}
    </ul>
  );
}
