import { initials } from '../lib/format';

export function Avatar({ name, strong }: { name: string; strong?: boolean }) {
  return (
    <span className="avatar" aria-hidden style={strong ? { color: 'var(--sm-ink-primary)' } : undefined}>
      {initials(name)}
    </span>
  );
}
