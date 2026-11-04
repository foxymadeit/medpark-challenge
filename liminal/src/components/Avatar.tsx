import { colorFor, PALETTE, type ColorKey } from '../lib/colors';
import { initials } from '../lib/format';

/** Initials in a soft per-person colour (stable by name). */
export function Avatar({ name, size, color, label, fill }: { name: string; strong?: boolean; size?: 'sm'; /** Override the per-name colour (e.g. neutral for unknown voices). */ color?: ColorKey; /** Own letters instead of the name's initials ("S1"). */ label?: string; /** A solid fill (a CSS colour token) with white letters, e.g. an unknown speaker's colour. */ fill?: string }) {
  const { bg, fg } = PALETTE[color ?? colorFor(name)];
  return (
    <span className={`avatar${size ? ` avatar--${size}` : ''}`} aria-hidden style={{ background: fill ?? bg, color: fill ? 'var(--sm-on-solid)' : fg, borderColor: 'transparent' }}>
      {label ?? initials(name)}
    </span>
  );
}
