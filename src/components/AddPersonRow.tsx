import { useId, useState } from 'react';
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
 * "+ Add participant" (template editor, MoM participants panel): a dashed + in the avatars' column;
 * a click opens a search box. Suggests saved people by first name / surname (by email once there's an @),
 * or offers to add the typed name, or just an email (a guest, format checked). `pool` is who can be suggested
 * (already added people left out); `known` is everyone with a name/email already, so the same one isn't created twice.
 * `guestButton` (MoM "Send to" panel): matches only in the list, and a full-width "Add guest" button under the field
 * saves what was typed instead of an "Add …" list option.
 */
export function AddPersonRow({ pool, known, onPick, onCreate, guestButton }: { pool: Person[]; known: { name: string; email?: string }[]; onPick: (p: Person) => void; onCreate: (typed: { name: string; email?: string }) => void; guestButton?: boolean }) {
  const { t } = useI18n();
  const id = useId();
  const [adding, setAdding] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [error, setError] = useState<string>();

  const q = query.trim();
  const lower = q.toLowerCase();
  const matches = q.includes('@') ? pool.filter((p) => p.email?.toLowerCase().startsWith(lower)).slice(0, 5) : suggestByName(pool, q, () => false, 5);
  const canCreate = !!q && !known.some((p) => p.name.toLowerCase() === lower || p.email?.toLowerCase() === lower);
  const offerCreate = canCreate && !guestButton; // as a list option; with guestButton it's the button
  const count = matches.length + (offerCreate ? 1 : 0);

  const reset = () => (setQuery(''), setActive(0), setError(undefined));
  const close = () => (setAdding(false), reset());
  const pick = (p: Person) => (onPick(p), reset());
  const create = () => {
    if (q.includes('@') && !isEmail(q)) return setError(t('common.emailInvalid'));
    onCreate(q.includes('@') ? { name: q, email: q } : { name: q });
    reset();
  };

  return (
    <div className="add-person">
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
      {/* Saved people first, "add new" last. Inline, so a modal or a scrolling panel never clips it. */}
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
          {offerCreate && (
            <li id={`${id}-opt-${matches.length}`} role="option" aria-selected={active === matches.length} className={`add-person__option add-person__create${active === matches.length ? ' is-active' : ''}`} onMouseEnter={() => setActive(matches.length)} onMouseDown={(e) => e.preventDefault()} onClick={create}>
              <span className="add-person__plus" aria-hidden>
                <PlusGlyph />
              </span>
              <span className="who__name truncate">{q.includes('@') ? t('owner.addEmail', { email: q }) : t('owner.addName', { name: q })}</span>
            </li>
          )}
        </ul>
      )}
      {adding && guestButton && (
        <Button block className="add-person__guest" disabled={!canCreate} onMouseDown={(e) => e.preventDefault()} onClick={create}>
          {t('common.addGuest')}
        </Button>
      )}
    </div>
  );
}
