import { useEffect, useId, useRef, useState } from 'react';
import { useI18n } from '../i18n/I18nProvider';
import { isEmail } from '../lib/format';
import { suggestByName } from '../lib/participants';
import type { Person } from '../types';
import { Avatar } from './Avatar';
import { Button } from './Button';
import { Highlight } from './ParticipantsField';

/** The thin "+" from Figma (10px, 1.5px lines): two bars, coloured by the text colour. */
export function PlusGlyph() {
  return <span className="plus-glyph" aria-hidden />;
}

/**
 * "+ Add participant" (template editor, MoM "Send to" panel): a dashed + in the avatars' column; a click opens a
 * search box (the + stays). Typing suggests saved people by first name / surname (by email once there's an @); a
 * full-width button under the field (`createLabel`: "Add guest", "New person") saves what was typed instead — a name,
 * or just an email (format checked). `pool` is who can be suggested (already added people left out); `known` is
 * everyone with a name/email already, so the same one isn't created twice.
 */
export function AddPersonRow({ pool, known, onPick, onCreate, createLabel }: { pool: Person[]; known: { name: string; email?: string }[]; onPick: (p: Person) => void; onCreate: (typed: { name: string; email?: string }) => void; createLabel: string }) {
  const { t } = useI18n();
  const id = useId();
  const [adding, setAdding] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [error, setError] = useState<string>();
  const box = useRef<HTMLDivElement>(null);
  // In a scrolling list (template editor) the field and the button under it come into view when typing starts.
  useEffect(() => {
    if (adding) box.current?.querySelector('.add-person__create')?.scrollIntoView({ block: 'nearest' });
  }, [adding]);

  const q = query.trim();
  const lower = q.toLowerCase();
  const matches = q.includes('@') ? pool.filter((p) => p.email?.toLowerCase().startsWith(lower)).slice(0, 5) : suggestByName(pool, q, () => false, 5);
  const canCreate = !!q && !known.some((p) => p.name.toLowerCase() === lower || p.email?.toLowerCase() === lower);
  const count = matches.length;

  const reset = () => (setQuery(''), setActive(0), setError(undefined));
  const close = () => (setAdding(false), reset());
  const pick = (p: Person) => (onPick(p), reset());
  const create = () => {
    if (q.includes('@') && !isEmail(q)) return setError(t('common.emailInvalid'));
    onCreate(q.includes('@') ? { name: q, email: q } : { name: q });
    reset();
  };

  return (
    <div className="add-person" ref={box}>
      <div className={`add-person__row${adding ? ' is-adding' : ''}`}>
        <span className="add-person__plus" aria-hidden>
          <PlusGlyph />
        </span>
        {adding ? (
          <input
            autoFocus
            className="add-person__input"
            placeholder={t('recipients.ph')}
            aria-label={t('common.addPerson')}
            role="combobox"
            aria-expanded={count > 0}
            aria-controls={`${id}-list`}
            aria-autocomplete="list"
            aria-activedescendant={count > 0 ? `${id}-opt-${active}` : undefined}
            aria-invalid={error ? true : undefined}
            value={query}
            onChange={(e) => (setQuery(e.target.value), setActive(0), setError(undefined))}
            onBlur={() => !q && close()}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') (e.preventDefault(), setActive((a) => Math.min(a + 1, count - 1)));
              else if (e.key === 'ArrowUp') (e.preventDefault(), setActive((a) => Math.max(a - 1, 0)));
              else if (e.key === 'Escape') (e.stopPropagation(), close());
              else if (e.key === 'Enter') {
                e.preventDefault();
                if (matches[active]) pick(matches[active]);
                else if (canCreate) create();
              }
            }}
          />
        ) : (
          <button type="button" className="add-person__open" onClick={() => setAdding(true)}>
            {t('common.addPerson')}
          </button>
        )}
      </div>
      {error && <p className="field__error add-person__error">{error}</p>}
      {/* Saved people that match. Inline, so a modal or a scrolling panel never clips it. */}
      {adding && count > 0 && (
        <ul id={`${id}-list`} role="listbox" aria-label={t('common.addPerson')} className="add-person__list">
          {matches.map((p, i) => (
            <li key={p.id} id={`${id}-opt-${i}`} role="option" aria-selected={i === active} className={`add-person__option${i === active ? ' is-active' : ''}`} onMouseEnter={() => setActive(i)} onMouseDown={(e) => e.preventDefault()} onClick={() => pick(p)}>
              <Avatar name={p.name} />
              <span className="who__text">
                <span className="who__name truncate">{q.includes('@') ? p.name : <Highlight text={p.name} query={lower} />}</span>
                <span className="who__sub truncate">{[p.role, p.email].filter(Boolean).join(' · ')}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
      {adding && (
        <Button block className="add-person__create" disabled={!canCreate} onMouseDown={(e) => e.preventDefault()} onClick={create}>
          {createLabel}
        </Button>
      )}
    </div>
  );
}
