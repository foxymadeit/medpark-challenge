import { PencilSimpleIcon, PlusIcon, XIcon } from '@phosphor-icons/react';
import { useState } from 'react';
import { useI18n } from '../i18n/I18nProvider';

/**
 * The MoM summary: key points as a list. With `onChange` each point can be edited in place
 * (pen on hover, Enter saves, Esc cancels, empty removes) and new points added.
 */
export function SummaryPoints({ points, onChange }: { points: string[]; onChange?: (points: string[]) => void }) {
  const { t } = useI18n();
  const [editing, setEditing] = useState<number | null>(null); // index; points.length = new point
  const [value, setValue] = useState('');

  const start = (i: number) => {
    setEditing(i);
    setValue(points[i] ?? '');
  };
  const cancel = () => setEditing(null);
  const save = () => {
    if (editing === null || !onChange) return;
    const v = value.trim();
    const next = [...points];
    if (editing >= points.length) v && next.push(v);
    else if (v) next[editing] = v;
    else next.splice(editing, 1);
    onChange(next);
    setEditing(null);
  };

  const editor = (
    <textarea
      className="input summary-points__input"
      aria-label={t('review.pointLabel')}
      placeholder={t('review.pointPh')}
      value={value}
      rows={2}
      autoFocus
      onChange={(e) => setValue(e.target.value)}
      onBlur={save}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && !e.shiftKey) (e.preventDefault(), save());
        else if (e.key === 'Escape') (e.stopPropagation(), cancel());
      }}
    />
  );

  return (
    <div className="summary-points">
      {points.length === 0 && editing === null && <p className="note">{t('review.noSummary')}</p>}
      <ul className="summary-points__list">
        {points.map((p, i) => (
          <li key={i} className="summary-points__item">
            {editing === i ? (
              editor
            ) : (
              <>
                <span className="summary-points__text">{p}</span>
                {onChange && (
                  <span className="summary-points__tools">
                    <button type="button" className="icon-btn" aria-label={t('review.editPoint')} onClick={() => start(i)}>
                      <PencilSimpleIcon size={16} aria-hidden />
                    </button>
                    <button type="button" className="icon-btn" aria-label={t('review.removePoint')} onClick={() => onChange(points.filter((_, j) => j !== i))}>
                      <XIcon size={16} aria-hidden />
                    </button>
                  </span>
                )}
              </>
            )}
          </li>
        ))}
        {editing === points.length && <li className="summary-points__item">{editor}</li>}
      </ul>
      {onChange && editing === null && (
        <button type="button" className="btn btn--ghost summary-points__add" onClick={() => start(points.length)}>
          <PlusIcon size={16} aria-hidden />
          {t('review.addPoint')}
        </button>
      )}
    </div>
  );
}
