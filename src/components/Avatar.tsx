import { initials } from '../lib/format';

/** Soft tint + dark text pairs (all ≥ 5.7:1). Separate from the speaker colours, which stay for dots and waveforms. */
const TINTS: [bg: string, fg: string][] = [
  ['#fbe3e6', '#8a2a3b'],
  ['#fde8d7', '#8a4a1c'],
  ['#fbf0cf', '#6e5208'],
  ['#e1f2e4', '#235e33'],
  ['#ddf1f0', '#1c5f5b'],
  ['#e2ecfd', '#274c8f'],
  ['#ece6fa', '#52408c'],
  ['#efebe4', '#5b544b'],
];

/** Same name → same colour everywhere (simple string hash). */
function tintFor(name: string) {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return TINTS[h % TINTS.length];
}

export function Avatar({ name }: { name: string; strong?: boolean }) {
  const [bg, fg] = tintFor(name);
  return (
    <span className="avatar" aria-hidden style={{ background: bg, color: fg, borderColor: 'transparent' }}>
      {initials(name)}
    </span>
  );
}
