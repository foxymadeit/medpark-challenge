import { UsersThreeIcon, XIcon } from '@phosphor-icons/react';
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { useI18n } from '../i18n/I18nProvider';
import type { DraftParticipant } from '../store/AppStore';
import { useStore } from '../store/AppStore';
import { Avatar } from './Avatar';

/**
 * Participants of the meeting as chips (name + ×), with an "Add name…" input at the end.
 * Enter or a comma adds what's typed; empty names and duplicates are ignored.
 * While typing, people from the directory are suggested (↑/↓ to pick one, or click).
 */
export function ParticipantsField({ participants, onChange }: { participants: DraftParticipant[]; onChange: (participants: DraftParticipant[]) => void }) {
  const { t } = useI18n();
  const { people } = useStore();
  const id = useId();
  const [input, setInput] = useState('');
  const [active, setActive] = useState(-1); // -1: Enter adds the typed name
  const wrap = useRef<HTMLDivElement>(null);
  const field = useRef<HTMLInputElement>(null);

  const q = input.trim().toLowerCase();
  const has = (name: string) => participants.some((p) => p.name.toLowerCase() === name.trim().toLowerCase());
  const suggestions = q ? people.filter((p) => !has(p.name) && [p.name, p.role, p.email].some((v) => v?.toLowerCase().includes(q))).slice(0, 6) : [];
  const showList = suggestions.length > 0;

  useEffect(() => setActive(-1), [q]);

  const add = (p: DraftParticipant) => {
    const name = p.name.trim();
    setInput('');
    if (!name || has(name)) return;
    onChange([...participants, { ...p, name }]);
  };
  const addTyped = () => {
    const known = people.find((p) => p.name.toLowerCase() === q);
    add(known ? { name: known.name, role: known.role } : { name: input });
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
      if (picked) add({ name: picked.name, role: picked.role });
      else addTyped();
    } else if (e.key === 'Escape') {
      setInput('');
    } else if (e.key === 'Backspace' && !input && participants.length) {
      onChange(participants.slice(0, -1));
    }
  };

  return (
    <div className="stack" style={{ gap: 10 }}>
      <label className="form-label" htmlFor={`${id}-in`}>
        {t('newMeeting.emails')}
      </label>
      <div className="emails-combo" ref={wrap}>
        {/* Clicking the empty part of the field puts the cursor in the input. */}
        <div className="emails-field" onMouseDown={(e) => e.target === e.currentTarget && (e.preventDefault(), field.current?.focus())}>
          <UsersThreeIcon size={20} aria-hidden />
          {participants.map((p) => (
            <span key={p.name} className="tag emails-field__tag" title={p.role}>
              {p.name}
              <button type="button" className="emails-field__remove" aria-label={t('newMeeting.removeEmail', { email: p.name })} onClick={() => onChange(participants.filter((x) => x.name !== p.name))}>
                <XIcon size={12} aria-hidden />
              </button>
            </span>
          ))}
          <input
            ref={field}
            id={`${id}-in`}
            className="emails-field__input"
            placeholder={t('newMeeting.emailsPh')}
            value={input}
            autoComplete="off"
            role="combobox"
            aria-expanded={showList}
            aria-controls={`${id}-list`}
            aria-autocomplete="list"
            aria-activedescendant={showList && active >= 0 ? `${id}-opt-${active}` : undefined}
            onChange={(e) => setInput(e.target.value.replace(',', ''))}
            onKeyDown={onKey}
            onBlur={(e) => {
              // Clicking a suggestion blurs the input first; let the click land.
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
                onMouseDown={(e) => e.preventDefault()} // keep focus in the input
                onClick={() => add({ name: p.name, role: p.role })}
              >
                <Avatar name={p.name} />
                <span className="who__text">
                  <span className="who__name truncate">{p.name}</span>
                  {p.role && <span className="who__sub truncate">{p.role}</span>}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
