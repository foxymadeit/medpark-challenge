import { EnvelopeSimpleIcon, XIcon } from '@phosphor-icons/react';
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { useI18n } from '../i18n/I18nProvider';
import { isEmail } from '../lib/format';
import { useStore } from '../store/AppStore';
import { Avatar } from './Avatar';

/**
 * Emails with suggestions from the participants list (ARIA combobox).
 * Focus shows everyone not added yet; typing filters by name, role or email.
 * Any other address can still be typed and confirmed with Enter or a comma.
 */
export function EmailsField({ emails, onChange }: { emails: string[]; onChange: (emails: string[]) => void }) {
  const { t } = useI18n();
  const { people, account } = useStore();
  const id = useId();
  const [input, setInput] = useState('');
  const [error, setError] = useState<string>();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const wrap = useRef<HTMLDivElement>(null);

  const q = input.trim().toLowerCase();
  const added = new Set(emails.map((e) => e.toLowerCase()));
  const suggestions = people
    .filter((p) => p.email && p.id !== account?.personId && !added.has(p.email.toLowerCase()))
    .filter((p) => !q || [p.name, p.email, p.role].some((v) => v?.toLowerCase().includes(q)))
    .slice(0, 6);
  const nameFor = (email: string) => people.find((p) => p.email?.toLowerCase() === email.toLowerCase())?.name;

  useEffect(() => setActive(0), [q]);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => !wrap.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const add = (values: string[]) => {
    onChange([...new Set([...emails, ...values])]);
    setInput('');
    setError(undefined);
  };

  const commitTyped = () => {
    const values = input.split(/[\s,;]+/).filter(Boolean);
    if (!values.length) return;
    if (values.some((v) => !isEmail(v))) return setError(t('common.emailInvalid'));
    add(values);
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    const list = open ? suggestions : [];
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!open) return setOpen(true);
      setActive((a) => Math.min(a + 1, list.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      // A highlighted suggestion wins unless what's typed is already a full email.
      if (list[active] && !isEmail(input.trim())) add([list[active].email!]);
      else commitTyped();
    } else if (e.key === 'Escape') {
      setOpen(false);
    } else if (e.key === 'Backspace' && !input && emails.length) {
      onChange(emails.slice(0, -1));
    }
  };

  const showList = open && suggestions.length > 0;

  return (
    <div className="stack" style={{ gap: 8 }}>
      <label className="t-strong" htmlFor={`${id}-in`}>
        {t('newMeeting.emails')}
      </label>
      <div className="emails-combo" ref={wrap}>
        <div className="emails-field">
          <EnvelopeSimpleIcon size={20} aria-hidden />
          {emails.map((email) => (
            <span key={email} className="tag emails-field__tag" title={email}>
              {nameFor(email) ?? email}
              <button type="button" className="emails-field__remove" aria-label={t('newMeeting.removeEmail', { email })} onClick={() => onChange(emails.filter((x) => x !== email))}>
                <XIcon size={12} aria-hidden />
              </button>
            </span>
          ))}
          <input
            id={`${id}-in`}
            type="email"
            className="emails-field__input"
            placeholder={emails.length ? '' : t('newMeeting.emailsPh')}
            value={input}
            role="combobox"
            aria-expanded={showList}
            aria-controls={`${id}-list`}
            aria-autocomplete="list"
            aria-activedescendant={showList ? `${id}-opt-${active}` : undefined}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? `${id}-err` : undefined}
            onChange={(e) => (setInput(e.target.value), setOpen(true), setError(undefined))}
            onFocus={() => setOpen(true)}
            onKeyDown={onKey}
            onBlur={(e) => {
              // Clicking a suggestion blurs the input first; let the click land.
              if (wrap.current?.contains(e.relatedTarget as Node)) return;
              if (input.trim()) commitTyped();
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
                onClick={() => add([p.email!])}
              >
                <Avatar name={p.name} />
                <span className="who__text">
                  <span className="who__name truncate">{p.name}</span>
                  <span className="who__sub truncate">
                    {p.role ? `${p.role} · ` : ''}
                    {p.email}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      {error && (
        <p id={`${id}-err`} className="field__error">
          {error}
        </p>
      )}
    </div>
  );
}
