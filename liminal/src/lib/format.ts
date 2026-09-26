import type { Lang } from '../i18n/I18nProvider';

const LOCALES: Record<Lang, string> = { en: 'en-GB', ro: 'ro-RO', ru: 'ru-RU' };
export const localeFor = (lang: Lang) => LOCALES[lang];

/** Parse "YYYY-MM-DD" as a local date (no timezone drift). */
export function parseDate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d);
}

export function toISODate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function todayISO(): string {
  return toISODate(new Date());
}

export function addDays(iso: string, days: number): string {
  const d = parseDate(iso);
  d.setDate(d.getDate() + days);
  return toISODate(d);
}

export function daysBetween(fromIso: string, toIso: string): number {
  return Math.round((parseDate(toIso).getTime() - parseDate(fromIso).getTime()) / 86_400_000);
}

// English follows Figma: "26 Sep" (en-GB would print "Sept" in current ICU).
const enMonth = (d: Date) => d.toLocaleDateString('en-US', { month: 'short' });

/** "26 Sep" */
export function formatDayMonth(iso: string, lang: Lang): string {
  const d = parseDate(iso);
  if (lang === 'en') return `${d.getDate()} ${enMonth(d)}`;
  return d.toLocaleDateString(localeFor(lang), { day: 'numeric', month: 'short' });
}

/** "26 Sep 2026" */
export function formatFullDate(iso: string, lang: Lang): string {
  const d = parseDate(iso);
  if (lang === 'en') return `${formatDayMonth(iso, lang)} ${d.getFullYear()}`;
  return d.toLocaleDateString(localeFor(lang), { day: 'numeric', month: 'short', year: 'numeric' });
}

/** "Mon 28 Sep" */
export function formatWeekdayDate(iso: string, lang: Lang): string {
  const d = parseDate(iso);
  const wd = d.toLocaleDateString(lang === 'en' ? 'en-US' : localeFor(lang), { weekday: 'short' });
  return `${wd} ${formatDayMonth(iso, lang)}`;
}

/** 00:42:18 */
export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
}

/** 0:27 */
export function formatCountdown(totalSeconds: number): string {
  const s = Math.max(0, Math.ceil(totalSeconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

/** 44 MB */
export function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${Math.round(bytes / (1024 * 1024))} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** "Dr. Ana Popescu" → "AP" (titles like Dr. are skipped). */
export function initials(name: string): string {
  const parts = name
    .replace(/\(.*?\)/g, '')
    .split(/\s+/)
    .filter((p) => p && !/^(dr|prof|mr|mrs|ms)\.?$/i.test(p));
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase();
}

export function isEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

export function uid(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * Deadline relative to the meeting date: "Same day", "Tomorrow", "In 3 days", "In a week", "In 2 weeks",
 * else just the weekday date. Returns the i18n key + vars; the concrete date is shown alongside.
 */
export function dueRelative(meetingIso: string, dueIso: string): { key: string; vars?: Record<string, number> } | null {
  const d = daysBetween(meetingIso, dueIso);
  if (d === 0) return { key: 'due.sameDay' };
  if (d === 1) return { key: 'due.tomorrow' };
  if (d >= 2 && d <= 6) return { key: 'due.inDays', vars: { count: d } };
  if (d === 7) return { key: 'due.inWeek' };
  if (d > 7 && d % 7 === 0) return { key: 'due.inWeeks', vars: { count: d / 7 } };
  return null;
}

/** Offsets offered when picking a deadline (days after the meeting). */
export const DUE_OFFSETS = [0, 1, 2, 3, 5, 7, 14];
