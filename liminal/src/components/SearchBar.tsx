import { MagnifyingGlassIcon } from '@phosphor-icons/react';
import { useEffect, useId, useState, type ReactNode } from 'react';
import { Avatar } from './Avatar';
import { Highlight } from './ParticipantsField';

export interface SearchOption {
  id: string;
  name: string;
  sub?: string;
}

/**
 * Search row above a list (History, Participants): the search field on the left, optional filters on the right.
 * With `options` it also suggests as you type (avatar, name with the typed letters underlined, email):
 * arrows + Enter or a click picks one, Esc closes the list.
 */
export function SearchBar({ value, onChange, placeholder, options, onPick, children }: { value: string; onChange: (value: string) => void; placeholder: string; options?: SearchOption[]; onPick?: (option: SearchOption) => void; children?: ReactNode }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const q = value.trim().toLowerCase();
  const list = open && q && options?.length ? options : [];

  useEffect(() => setActive(0), [q]);

  const pick = (o: SearchOption) => (onPick?.(o), setOpen(false));

  return (
    <div className="search-bar">
      <div className="emails-combo search-bar__combo">
        <label className="search">
          <MagnifyingGlassIcon size={16} aria-hidden />
          <span className="sr-only">{placeholder}</span>
          <input
            type="search"
            placeholder={placeholder}
            value={value}
            onChange={(e) => (onChange(e.target.value), setOpen(true))}
            onFocus={() => setOpen(true)}
            onBlur={() => setOpen(false)}
            {...(options && {
              role: 'combobox',
              'aria-expanded': list.length > 0,
              'aria-controls': `${id}-list`,
              'aria-autocomplete': 'list' as const,
              'aria-activedescendant': list.length ? `${id}-opt-${active}` : undefined,
              onKeyDown: (e) => {
                if (e.key === 'Escape') return setOpen(false);
                if (!list.length) return;
                if (e.key === 'ArrowDown') (e.preventDefault(), setActive((a) => Math.min(a + 1, list.length - 1)));
                else if (e.key === 'ArrowUp') (e.preventDefault(), setActive((a) => Math.max(a - 1, 0)));
                else if (e.key === 'Enter') (e.preventDefault(), pick(list[active]));
              },
            })}
          />
        </label>
        {list.length > 0 && (
          <ul id={`${id}-list`} role="listbox" aria-label={placeholder} className="emails-combo__list">
            {list.map((o, i) => (
              <li key={o.id} id={`${id}-opt-${i}`} role="option" aria-selected={i === active} className={`emails-combo__option${i === active ? ' is-active' : ''}`} onMouseEnter={() => setActive(i)} onMouseDown={(e) => e.preventDefault()} onClick={() => pick(o)}>
                <Avatar name={o.name} />
                <span className="who__text">
                  <span className="who__name truncate">{q.includes('@') ? o.name : <Highlight text={o.name} query={q} />}</span>
                  {o.sub && <span className="who__sub truncate">{o.sub}</span>}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      {children}
    </div>
  );
}
