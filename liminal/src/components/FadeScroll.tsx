import { useLayoutEffect, useRef, useState, type ReactNode } from 'react';

/**
 * A scrolling box whose top / bottom edge fades into the card (28px, card colour) only while there's more text that
 * way: no top fade at the start, no bottom fade at the end. The fades don't catch clicks or text selection.
 */
export function FadeScroll({ className, children }: { className?: string; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState({ above: false, below: false });

  // Re-measured after every render (content changed), on scroll and on resize; state only changes when an edge flips.
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const update = () => {
      const above = el.scrollTop > 1;
      const below = el.scrollTop + el.clientHeight < el.scrollHeight - 1;
      setEdges((e) => (e.above === above && e.below === below ? e : { above, below }));
    };
    update();
    el.addEventListener('scroll', update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => (el.removeEventListener('scroll', update), ro.disconnect());
  });

  return (
    <div className={`fade-scroll${edges.above ? ' has-above' : ''}${edges.below ? ' has-below' : ''}`}>
      <div ref={box} className={className}>
        {children}
      </div>
    </div>
  );
}
