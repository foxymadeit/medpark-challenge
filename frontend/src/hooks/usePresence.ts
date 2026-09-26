import { useEffect, useState } from "react";

/** Keeps something on screen for `exitMs` after it is told to close, so it
 * can fade out instead of vanishing. Returns whether to render it and
 * whether it is on its way out. */
export function usePresence(open: boolean, exitMs = 120) {
  const [present, setPresent] = useState(open);
  if (open && !present) setPresent(true);
  useEffect(() => {
    if (open || !present) return;
    const timer = setTimeout(() => setPresent(false), exitMs);
    return () => clearTimeout(timer);
  }, [open, present, exitMs]);
  return { present, closing: present && !open };
}
