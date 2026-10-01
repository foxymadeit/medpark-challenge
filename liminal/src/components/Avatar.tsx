import { colorFor, PALETTE, type ColorKey } from '../lib/colors';
import { initials } from '../lib/format';

/** Initials in a soft per-person colour (stable by name). */
export function Avatar({ name, size, color }: { name: string; strong?: boolean; size?: 'sm'; /** Override the per-name colour (e.g. neutral for unknown voices). */ color?: ColorKey }) {
  const { bg, fg } = PALETTE[color ?? colorFor(name)];
  return (
    <span className={`avatar${size ? ` avatar--${size}` : ''}`} aria-hidden style={{ background: bg, color: fg, borderColor: 'transparent' }}>
      {initials(name)}
    </span>
  );
}
