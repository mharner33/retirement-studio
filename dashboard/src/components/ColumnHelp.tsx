import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { place, type Position } from "./popover";

interface Props {
  label: string;
  help: string;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
}

/** A column heading with an ⓘ button that shows how the column is worked
 * out. Opens on click or Enter; Escape or a click elsewhere closes it. The
 * popover is fixed to the window so the table's scrolling never cuts it off. */
export function ColumnHelp({ label, help, open, onToggle, onClose }: Readonly<Props>) {
  const id = useId();
  const wrap = useRef<HTMLSpanElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const popover = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState<Position | null>(null);

  useLayoutEffect(() => {
    if (!open) return undefined;
    const update = (): void => {
      if (!button.current || !popover.current) return;
      setPos(
        place(
          button.current.getBoundingClientRect(),
          popover.current.offsetWidth,
          window.innerWidth,
        ),
      );
    };
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const key = (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        onClose();
        button.current?.focus();
      }
    };
    const click = (e: MouseEvent): void => {
      if (!wrap.current?.contains(e.target as Node)) onClose();
    };
    document.addEventListener("keydown", key);
    document.addEventListener("mousedown", click);
    return () => {
      document.removeEventListener("keydown", key);
      document.removeEventListener("mousedown", click);
    };
  }, [open, onClose]);

  return (
    <span className="column-help" ref={wrap}>
      {label}
      <button
        ref={button}
        type="button"
        className="help-button"
        aria-label={`How ${label} is worked out`}
        aria-expanded={open}
        aria-controls={id}
        onClick={onToggle}
      >
        ⓘ
      </button>
      {open && (
        <span
          id={id}
          ref={popover}
          role="note"
          className="help-popover"
          style={pos ? { top: pos.top, left: pos.left } : { visibility: "hidden" }}
        >
          {help}
        </span>
      )}
    </span>
  );
}
