import { CheckIcon, ClockIcon, PencilSimpleIcon } from '@phosphor-icons/react';
import { useI18n } from '../i18n/I18nProvider';
import type { MeetingStatus } from '../types';

const ICONS = { needs_review: PencilSimpleIcon, sent: CheckIcon, processing: ClockIcon };

export function StatusTag({ status }: { status: MeetingStatus }) {
  const { t } = useI18n();
  const Icon = ICONS[status];
  return (
    <span className="status-tag">
      <Icon size={14} aria-hidden />
      {t(`status.${status}`)}
    </span>
  );
}
