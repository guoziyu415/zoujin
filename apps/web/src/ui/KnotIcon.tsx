// The small knotted-cord mark of a promise (ux-design 6.3, 10.3): a loop tied on a short cord. Drawn in the text
// colour so it sits in a line of ink or on a toast.
export function KnotIcon({ label }: { label?: string }) {
  return (
    <svg
      className="knot"
      viewBox="0 0 16 16"
      width="14"
      height="14"
      {...(label
        ? { role: "img", "aria-label": label }
        : { "aria-hidden": true })}
    >
      <path
        d="M1 11 C4 11 5 9 6.5 7.5 M9.5 7.5 C11 9 12 11 15 11 M6.5 7.5 C5 5.5 6 3 8 3 C10 3 11 5.5 9.5 7.5 C8.6 8.6 7.4 8.6 6.5 7.5 Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}
