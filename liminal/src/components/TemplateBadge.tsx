import { PALETTE, type ColorKey } from '../lib/colors';
import type { MeetingType } from '../types';
import { MeetingTypeIcon } from './MeetingTypeIcon';

/** Template colour + its meeting-type icon: recognisable at a glance. */
export function TemplateBadge({ color, type, size = 40 }: { color: ColorKey; type: MeetingType; size?: number }) {
  return (
    <span className="tpl-badge" aria-hidden style={{ width: size, height: size, background: PALETTE[color].solid, color: 'var(--sm-on-solid)' }}>
      <MeetingTypeIcon type={type} size={Math.round(size / 2)} />
    </span>
  );
}
