import { BriefcaseIcon, ClipboardTextIcon, StethoscopeIcon, type IconProps } from '@phosphor-icons/react';
import type { MeetingType } from '../types';

const ICONS = { medical: StethoscopeIcon, executive: BriefcaseIcon, administrative: ClipboardTextIcon } as const;

/** One recognisable icon per meeting type: stethoscope, briefcase, clipboard. */
export function MeetingTypeIcon({ type, size = 16, ...rest }: { type: MeetingType; size?: number } & IconProps) {
  const Icon = ICONS[type];
  return <Icon size={size} aria-hidden {...rest} />;
}
