import { UserPlusIcon } from '@phosphor-icons/react';
import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useI18n } from '../i18n/I18nProvider';
import { isEmail, uid } from '../lib/format';
import { suggestByName } from '../lib/participants';
import { useStore } from '../store/AppStore';
import type { Meeting, ParticipantSnapshot } from '../types';
import { Avatar } from './Avatar';
import { Highlight } from './ParticipantsField';

type Option = { kind: 'person'; snap: ParticipantSnapshot } | { kind: 'new'; snap: ParticipantSnapshot; label: string };

/**
 * Task owner while a task is being edited: the same avatar + name as in the read row (one line, ellipsis), as one button.
 * An unknown voice ("Speaker 1") opens the list with nothing selected, so the reviewer maps it to a participant. It opens a list with a search box:
 * the meeting's participants (empty search), saved participants by name as you type, or a new name /
 * an email only (a guest) — the same rules as the Recipients field. Picking replaces the whole owner.
 */
export function OwnerPicker({ meeting, ownerId, name, badge, onPick }: { meeting: Meeting; ownerId: string; name: string; badge?: { label: string; fill: string }; onPick: (owner: ParticipantSnapshot) => void }) {
  const { t } = useI18n();
  const { people } = useStore();
  const id = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [error, setError] = useState<string>();
  const wrap = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);

  const q = query.trim();

  // Everyone pickable: this meeting's participants first, then the saved directory (once each).
  const pool: ParticipantSnapshot[] = [
    ...meeting.participants,
    ...people.filter((p) => !meeting.participants.some((x) => x.personId === p.id)).map((p) => ({ personId: p.id, name: p.name, email: p.email, roleThen: p.role })),
  ];
  const matches = q ? (q.includes('@') ? pool.filter((p) => p.email?.toLowerCase().startsWith(q.toLowerCase())) : suggestByName(pool, q, () => false)) : meeting.participants;
  const exact = pool.some((p) => p.name.toLowerCase() === q.toLowerCase() || p.email?.toLowerCase() === q.toLowerCase());
  const options: Option[] = matches.map((snap) => ({ kind: 'person' as const, snap }));
  if (q && !exact) {
    // Nobody like that yet: offer to add them (a guest, with the email when one was typed).
    const guest = q.includes('@') ? { personId: uid('guest'), name: q, email: q, roleThen: '' } : { personId: uid('guest'), name: q, roleThen: '' };
    options.push({ kind: 'new', snap: guest, label: q.includes('@') ? t('owner.addEmail', { email: q }) : t('owner.addName', { name: q }) });
  }

  // Highlight the current owner; none for an unknown voice (no option is theirs) until the arrows move.
  const ownIndex = options.findIndex((o) => o.kind === 'person' && o.snap.personId === ownerId);
  useEffect(() => setActive(q ? 0 : ownIndex), [q, open]); // eslint-disable-line react-hooks/exhaustive-deps
  // The list is pinned to the window (it lives inside a scrolling container that would clip it):
  // below the button, or above it when there's no room below. Scrolling anything else closes it.
  const [pos, setPos] = useState<{ left: number; top?: number; bottom?: number }>({ left: 0 });
  useLayoutEffect(() => {
    if (!open || !button.current) return;
    const r = button.current.getBoundingClientRect();
    const below = innerHeight - r.bottom;
    const left = Math.max(8, Math.min(r.left, innerWidth - 320 - 8));
    setPos(below >= 360 || below >= r.top ? { left, top: r.bottom + 4 } : { left, bottom: innerHeight - r.top + 4 });
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => !wrap.current?.contains(e.target as Node) && setOpen(false);
    const onScroll = (e: Event) => !wrap.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener('mousedown', onDown);
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', () => setOpen(false), { once: true });
    return () => (document.removeEventListener('mousedown', onDown), window.removeEventListener('scroll', onScroll, true));
  }, [open]);

  const close = () => (setOpen(false), setQuery(''), setError(undefined), button.current?.focus());
  const pick = (o: Option) => {
    if (o.kind === 'new' && o.snap.email && !isEmail(o.snap.email)) return setError(t('common.emailInvalid'));
    onPick(o.snap);
    close();
  };
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') (e.preventDefault(), setActive((a) => Math.min(a + 1, options.length - 1)));
    else if (e.key === 'ArrowUp') (e.preventDefault(), setActive((a) => Math.max(a - 1, 0)));
    else if (e.key === 'Enter') (e.preventDefault(), options[active] && pick(options[active]));
    else if (e.key === 'Escape') (e.stopPropagation(), close());
  };

  return (
    <div className="owner-picker" ref={wrap}>
      <button ref={button} type="button" className="owner-picker__button" aria-haspopup="listbox" aria-expanded={open} aria-label={t('owner.change', { name })} onClick={() => (open ? close() : setOpen(true))}>
        <Avatar name={name} {...badge} />
        <span className="task-owner__name truncate">{name}</span>
      </button>
      {open && (
        <div className="dropdown__list owner-picker__panel" style={{ position: 'fixed', ...pos }}>
          <input
            autoFocus
            className="input input--inline owner-picker__search"
            placeholder={t('recipients.ph')}
            value={query}
            role="combobox"
            aria-expanded
            aria-controls={`${id}-list`}
            aria-activedescendant={options[active] ? `${id}-opt-${active}` : undefined}
            aria-label={t('owner.search')}
            aria-invalid={error ? true : undefined}
            onChange={(e) => (setQuery(e.target.value), setError(undefined))}
            onKeyDown={onKey}
          />
          {error && <p className="field__error owner-picker__error">{error}</p>}
          <ul id={`${id}-list`} role="listbox" aria-label={t('owner.search')} className="owner-picker__list">
            {options.map((o, i) => (
              <li
                key={o.kind === 'new' ? 'new' : o.snap.personId}
                id={`${id}-opt-${i}`}
                role="option"
                aria-selected={o.kind === 'person' && o.snap.personId === ownerId}
                className={`emails-combo__option${i === active ? ' is-active' : ''}`}
                onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pick(o)}
              >
                {o.kind === 'new' ? (
                  <>
                    <span className="owner-picker__new" aria-hidden>
                      <UserPlusIcon size={16} />
                    </span>
                    <span className="who__name truncate">{o.label}</span>
                  </>
                ) : (
                  <>
                    <Avatar name={o.snap.name} />
                    <span className="who__text">
                      <span className="who__name truncate">{q && !q.includes('@') ? <Highlight text={o.snap.name} query={q.toLowerCase()} /> : o.snap.name}</span>
                      <span className="who__sub truncate">{[o.snap.roleThen, o.snap.email].filter(Boolean).join(' · ')}</span>
                    </span>
                  </>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
