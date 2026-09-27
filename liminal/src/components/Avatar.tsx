import { colorFor, PALETTE } from '../lib/colors';
import { initials } from '../lib/format';

/** Initials in a soft per-person colour (stable by name). */
export function Avatar({ name }: { name: string; strong?: boolean }) {
  const { bg, fg } = PALETTE[colorFor(name)];
  return (
    <span className="avatar" aria-hidden style={{ background: bg, color: fg, borderColor: 'transparent' }}>
      {initials(name)}
    </span>
  );
}
