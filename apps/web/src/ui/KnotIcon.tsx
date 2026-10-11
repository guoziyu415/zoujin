// The small knotted-cord mark of a promise (ux-design 6.3, 10.3): a loop whose two ends cross under it and hang down
// left and right, tied (not a head and shoulders). Drawn in the text colour at the text's size, so it sits in a line
// of ink or on a toast.
export function KnotIcon({ label }: { label?: string }) {
  return (
    <svg
      className="knot"
      viewBox="0 0 16 16"
      width="1em"
      height="1em"
      {...(label
        ? { role: "img", "aria-label": label }
        : { "aria-hidden": true })}
    >
      <path
        d="M3.5 15 L9.6 7.8 C11.1 6 10.4 2.2 8 2.2 C5.6 2.2 4.9 6 6.4 7.8 L12.5 15 M7.2 10.6 L8.8 10.6"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}
