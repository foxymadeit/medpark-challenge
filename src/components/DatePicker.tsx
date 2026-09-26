import { CalendarBlankIcon, CaretDownIcon, CaretLeftIcon, CaretRightIcon } from '@phosphor-icons/react';
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { useI18n } from '../i18n/I18nProvider';
import { addDays, formatFullDate, localeFor, parseDate, toISODate, todayISO } from '../lib/format';

/** First Monday on or before the 1st of the month (weeks start on Monday in MD/RO/RU). */
function gridStart(month: Date): Date {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const shift = (first.getDay() + 6) % 7;
  first.setDate(first.getDate() - shift);
  return first;
}

/**
 * Date chip + calendar popover in the app's own style (the native picker looks different on every OS).
 * Keyboard: ← → ↑ ↓ days/weeks, PageUp/PageDown months, Home/End week, Enter picks, Esc closes.
 */
export function DatePicker({ value, onChange, label }: { value: string; onChange: (iso: string) => void; label: string }) {
  const { t, lang } = useI18n();
  const id = useId();
  const [open, setOpen] = useState(false);
  const [focus, setFocus] = useState(value); // day with keyboard focus
  const wrap = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const today = todayISO();
  const locale = lang === 'en' ? 'en-US' : localeFor(lang);

  const month = parseDate(focus);
  const start = gridStart(month);
  const days = Array.from({ length: 42 }, (_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    return d;
  });
  const weekdays = days.slice(0, 7).map((d) => d.toLocaleDateString(locale, { weekday: 'short' }).slice(0, 2));
  const monthLabel = month.toLocaleDateString(locale, { month: 'long', year: 'numeric' });

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => !wrap.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  // Keep DOM focus on the focused day while the grid is open.
  useEffect(() => {
    if (open) wrap.current?.querySelector<HTMLButtonElement>(`[data-day="${focus}"]`)?.focus();
  }, [open, focus]);

  const shiftMonth = (n: number) => {
    const d = parseDate(focus);
    const target = new Date(d.getFullYear(), d.getMonth() + n, 1);
    const last = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
    target.setDate(Math.min(d.getDate(), last));
    setFocus(toISODate(target));
  };

  const pick = (iso: string) => {
    onChange(iso);
    setOpen(false);
    button.current?.focus();
  };

  const onGridKey = (e: KeyboardEvent) => {
    const moves: Record<string, () => void> = {
      ArrowLeft: () => setFocus(addDays(focus, -1)),
      ArrowRight: () => setFocus(addDays(focus, 1)),
      ArrowUp: () => setFocus(addDays(focus, -7)),
      ArrowDown: () => setFocus(addDays(focus, 7)),
      PageUp: () => shiftMonth(-1),
      PageDown: () => shiftMonth(1),
      Home: () => setFocus(addDays(focus, -((parseDate(focus).getDay() + 6) % 7))),
      End: () => setFocus(addDays(focus, 6 - ((parseDate(focus).getDay() + 6) % 7))),
    };
    if (e.key === 'Escape') {
      e.stopPropagation();
      setOpen(false);
      button.current?.focus();
    } else if (moves[e.key]) {
      e.preventDefault();
      moves[e.key]();
    }
  };

  return (
    <div className="datepicker" ref={wrap}>
      <button
        ref={button}
        type="button"
        className="date-chip"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={`${label}: ${formatFullDate(value, lang)}`}
        onClick={() => (setFocus(value), setOpen((o) => !o))}
      >
        <CalendarBlankIcon size={18} aria-hidden />
        <span className="date-chip__value">{formatFullDate(value, lang)}</span>
        {value === today && <span className="date-chip__tag">{t('review.today')}</span>}
        <CaretDownIcon size={14} aria-hidden />
      </button>

      {open && (
        <div className="datepicker__panel" role="dialog" aria-modal="false" aria-labelledby={`${id}-m`} onKeyDown={onGridKey}>
          <div className="datepicker__head">
            <p id={`${id}-m`} className="datepicker__month" aria-live="polite">
              {monthLabel}
            </p>
            <button type="button" className="icon-btn" aria-label={t('date.prevMonth')} onClick={() => shiftMonth(-1)}>
              <CaretLeftIcon size={16} aria-hidden />
            </button>
            <button type="button" className="icon-btn" aria-label={t('date.nextMonth')} onClick={() => shiftMonth(1)}>
              <CaretRightIcon size={16} aria-hidden />
            </button>
          </div>
          <table className="datepicker__grid" role="grid" aria-labelledby={`${id}-m`}>
            <thead>
              <tr>
                {weekdays.map((w, i) => (
                  <th key={i} scope="col" abbr={w}>
                    {w}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 6 }, (_, row) => (
                <tr key={row}>
                  {days.slice(row * 7, row * 7 + 7).map((d) => {
                    const iso = toISODate(d);
                    const outside = d.getMonth() !== month.getMonth();
                    const cls = ['datepicker__day', outside && 'is-outside', iso === today && 'is-today', iso === value && 'is-selected'].filter(Boolean).join(' ');
                    return (
                      <td key={iso}>
                        <button
                          type="button"
                          className={cls}
                          data-day={iso}
                          tabIndex={iso === focus ? 0 : -1}
                          aria-pressed={iso === value}
                          aria-current={iso === today ? 'date' : undefined}
                          aria-label={formatFullDate(iso, lang)}
                          onClick={() => pick(iso)}
                        >
                          {d.getDate()}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="datepicker__foot">
            <button type="button" className="link-btn" onClick={() => pick(today)}>
              {t('review.today')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
