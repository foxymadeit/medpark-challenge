import { useLayoutEffect, useRef, useState } from 'react';

/**
 * Does a line of a start tile fit in full? Render `text` in a hidden `.fit-probe` span with this ref, and use the short
 * copy only when it doesn't. The width differs per language, so one breakpoint can't decide it. `reserve` is what the rest
 * of the line needs.
 */
export function useFitsTile(text: string, reserve = 0) {
  const probe = useRef<HTMLSpanElement>(null);
  const [fits, setFits] = useState(true);

  useLayoutEffect(() => {
    const el = probe.current;
    const tile = el?.closest('.start-tile');
    if (!el || !tile) return;
    const measure = () => {
      const { paddingLeft, paddingRight } = getComputedStyle(tile);
      const room = tile.clientWidth - parseFloat(paddingLeft) - parseFloat(paddingRight);
      setFits(el.getBoundingClientRect().width + reserve <= room);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(tile);
    void document.fonts.ready.then(measure); // the probe is narrower in the fallback font
    return () => observer.disconnect();
  }, [text, reserve]);

  return { probe, fits };
}
