const GAP = 6;
const EDGE = 8;

export interface Position {
  top: number;
  left: number;
}

/** Below the button, lined up with its right edge, kept at least 8px inside
 * the window on both sides. */
export function place(button: DOMRect, width: number, windowWidth: number): Position {
  const max = windowWidth - width - EDGE;
  return {
    top: button.bottom + GAP,
    left: Math.max(EDGE, Math.min(button.right - width, max)),
  };
}
