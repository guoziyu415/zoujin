// A full page over the world (frontend-design 10.4, 13): opaque paper, a dialog for screen readers, the focus goes to
// its heading when it opens and back to where it was when it closes, Escape closes it.
import { useEffect, useRef, type ReactNode } from "react";
import { copy } from "./copy";

export function FullPage({
  title,
  className,
  onClose,
  children,
}: {
  title: string;
  className: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const head = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    const back = document.activeElement as HTMLElement | null;
    head.current?.focus();
    return () => back?.focus?.();
  }, []);
  useEffect(() => {
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose]);
  const id = `${className.split(" ")[0]}-title`;
  return (
    <section
      className={`page overlay ${className}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby={id}
    >
      <div className="page-body">
        <header className="page-head">
          <h1 id={id} ref={head} tabIndex={-1}>
            {title}
          </h1>
          <button className="page-close" onClick={onClose}>
            {copy["common.close"]}
          </button>
        </header>
        {children}
      </div>
    </section>
  );
}
