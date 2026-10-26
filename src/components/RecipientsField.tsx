import { EnvelopeSimpleIcon, XIcon } from '@phosphor-icons/react';
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { useI18n } from '../i18n/I18nProvider';
import { isEmail, uid } from '../lib/format';
import { suggestByName } from '../lib/participants';
import { useStore } from '../store/AppStore';
import type { Meeting, ParticipantSnapshot, Person } from '../types';
import { Avatar } from './Avatar';
import { Highlight } from './ParticipantsField';

/**
 * Who gets the MoM, edited right before sending (Review). Chips: a person's name, or a guest's email.
 * Add: pick a saved participant (suggested as you type), type a new name, or type just an email
 * (format checked) for a guest. The organizer and people who own an action item can't be removed.
 */
export function RecipientsField({ meeting, onChange }: { meeting: Meeting; onChange: (participants: ParticipantSnapshot[]) => void }) {
  const { t } = useI18n();
  const { account, people } = useStore();
  const id = useId();
  const [input, setInput] = useState('');
  const [active, setActive] = useState(-1); // -1: Enter adds what's typed
  const [error, setError] = useState<string>();
  const wrap = useRef<HTMLDivElement>(null);
  const field = useRef<HTMLInputElement>(null);

  const list = meeting.participants;
  const owners = new Set(meeting.tasks.map((x) => x.ownerId));
  const q = input.trim().toLowerCase();
  const isIn = (p: { id?: string; name: string; email?: string }) =>
    list.some((x) => (p.id && x.personId === p.id) || x.name.toLowerCase() === p.name.toLowerCase() || (!!p.email && x.email?.toLowerCase() === p.email.toLowerCase()));
  const suggestions = q.includes('@') ? [] : suggestByName(people, q, (p) => isIn(p));
  const showList = suggestions.length > 0;

  useEffect(() => setActive(-1), [q]);

  const snapshot = (p: Person): ParticipantSnapshot => ({ personId: p.id, name: p.name, email: p.email, roleThen: p.role });
  const addPerson = (p: Person) => {
    setInput('');
    setError(undefined);
    if (!isIn(p)) onChange([...list, snapshot(p)]);
  };
  const addTyped = () => {
    const text = input.trim();
    if (!text) return;
    if (text.includes('@')) {
      // Only an email: a guest who gets the minutes at that address.
      if (!isEmail(text)) return setError(t('common.emailInvalid'));
      const known = people.find((p) => p.email?.toLowerCase() === text.toLowerCase());
      if (known) return addPerson(known);
      setInput('');
      if (!isIn({ name: text, email: text })) onChange([...list, { personId: uid('guest'), name: text, email: text, roleThen: '' }]);
      return;
    }
    const known = people.find((p) => p.name.toLowerCase() === q);
    if (known) return addPerson(known);
    setInput('');
    if (!isIn({ name: text })) onChange([...list, { personId: uid('guest'), name: text, roleThen: '' }]);
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown' && showList) {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp' && showList) {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, -1));
    } else if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      const picked = suggestions[active];
      if (picked) addPerson(picked);
      else addTyped();
    } else if (e.key === 'Escape') {
      setInput('');
      setError(undefined);
    }
  };

  // Why a chip can't be removed (shown as its × tooltip), or nothing.
  const lockReason = (p: ParticipantSnapshot) => (p.personId === account?.personId ? t('recipients.organizer') : owners.has(p.personId) ? t('recipients.owner') : undefined);

  return (
    <div className="stack" style={{ gap: 10 }}>
      <div className="emails-combo" ref={wrap}>
        <div className="emails-field" onMouseDown={(e) => e.target === e.currentTarget && (e.preventDefault(), field.current?.focus())}>
          <EnvelopeSimpleIcon size={20} aria-hidden />
          {list.map((p) => {
            const guest = p.personId.startsWith('guest');
            const label = guest && p.email ? p.email : p.name; // a guest added by email shows the email
            const lock = lockReason(p);
            return (
              <span key={p.personId} className="tag emails-field__tag" title={p.email ?? t('review.noEmail')}>
                {label}
                {!p.email && <span className="c-secondary"> · {t('review.noEmail')}</span>}
                <button
                  type="button"
                  className="emails-field__remove"
                  aria-label={lock ?? t('newMeeting.removeEmail', { email: label })}
                  title={lock}
                  disabled={!!lock}
                  onClick={() => onChange(list.filter((x) => x.personId !== p.personId))}
                >
                  <XIcon size={12} aria-hidden />
                </button>
              </span>
            );
          })}
          <input
            ref={field}
            className="emails-field__input"
            placeholder={t('recipients.ph')}
            value={input}
            autoComplete="off"
            role="combobox"
            aria-label={t('recipients.title')}
            aria-expanded={showList}
            aria-controls={`${id}-list`}
            aria-autocomplete="list"
            aria-activedescendant={showList && active >= 0 ? `${id}-opt-${active}` : undefined}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? `${id}-err` : undefined}
            onChange={(e) => (setInput(e.target.value.replace(',', '')), setError(undefined))}
            onKeyDown={onKey}
            onBlur={(e) => {
              if (wrap.current?.contains(e.relatedTarget as Node)) return;
              if (input.trim()) addTyped();
            }}
          />
        </div>
        {showList && (
          <ul id={`${id}-list`} className="emails-combo__list" role="listbox" aria-label={t('newMeeting.suggestions')}>
            {suggestions.map((p, i) => (
              <li
                key={p.id}
                id={`${id}-opt-${i}`}
                role="option"
                aria-selected={i === active}
                className={`emails-combo__option${i === active ? ' is-active' : ''}`}
                onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => addPerson(p)}
              >
                <Avatar name={p.name} />
                <span className="who__text">
                  <span className="who__name truncate">
                    <Highlight text={p.name} query={q} />
                  </span>
                  <span className="who__sub truncate">{[p.role, p.email].filter(Boolean).join(' · ')}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      {error && (
        <p id={`${id}-err`} className="field__error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
