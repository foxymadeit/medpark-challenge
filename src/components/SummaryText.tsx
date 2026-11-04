import { PencilSimpleIcon } from '@phosphor-icons/react';
import { useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { useI18n } from '../i18n/I18nProvider';
import { summaryProse } from '../lib/meeting';
import { FadeScroll } from './FadeScroll';

/**
 * The MoM summary as one running text. With `onChange` one pen beside the heading edits the whole text in place:
 * Enter or leaving the field saves (Shift+Enter is a new line), Esc cancels.
 */
export function SummaryText({ points, onChange, head }: { points: string[]; onChange?: (points: string[]) => void; /** Heading; when editable, the pen sits on its right. */ head?: ReactNode }) {
  const { t } = useI18n();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState('');
  const input = useRef<HTMLTextAreaElement>(null);
  const text = summaryProse(points);

  // As tall as its text (+ the 1px border), so the summary keeps its height while editing.
  useLayoutEffect(() => {
    const el = input.current;
    if (!el) return;
    el.style.height = '0';
    el.style.height = `${el.scrollHeight + 2}px`;
  }, [editing, value]);

  const start = () => (setValue(text), setEditing(true));
  const save = () => {
    const v = value.trim();
    if (v !== text) onChange?.(v ? [v] : []);
    setEditing(false);
  };

  return (
    <>
      {head && (
        <div className="summary-head">
          {head}
          {onChange && (
            <button type="button" className="icon-btn task-edit-btn" aria-label={t('review.editSummary')} title={t('review.editSummary')} onClick={start} disabled={editing}>
              <PencilSimpleIcon size={20} aria-hidden />
            </button>
          )}
        </div>
      )}
      <FadeScroll className="summary-text">
        {editing ? (
          <textarea
            ref={input}
            autoFocus
            className="input summary-text__input"
            aria-label={t('review.summary')}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onBlur={save}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) (e.preventDefault(), save());
              else if (e.key === 'Escape') (e.stopPropagation(), setEditing(false));
            }}
          />
        ) : text ? (
          <p className="summary-text__body">{text}</p>
        ) : (
          <p className="note">{t('review.noSummary')}</p>
        )}
      </FadeScroll>
    </>
  );
}
