import { CaretDownIcon, CheckIcon } from '@phosphor-icons/react';
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';

export interface DropdownOption {
  value: string;
  label: string;
}

interface Props {
  label: string; // accessible name
  value: string;
  options: DropdownOption[];
  onChange: (value: string) => void;
  /** Adds a last "+ Custom …" entry that turns into a text input. */
  customLabel?: string;
  customPlaceholder?: string;
  width?: number | string;
  variant?: 'row' | 'field';
  disabled?: boolean;
  labelledBy?: string;
  /** Shown as a tooltip when disabled. */
  disabledReason?: string;
}

const CUSTOM = '__custom__';

/** Select-like listbox (Figma "Select" + "Dropdown · role"). Keyboard: ↑ ↓ Home End Enter Esc. */
export function Dropdown({ label, value, options, onChange, customLabel, customPlaceholder, width, variant = 'row', disabled, labelledBy, disabledReason }: Props) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [custom, setCustom] = useState(false);
  const [customValue, setCustomValue] = useState('');
  const all = customLabel ? [...options, { value: CUSTOM, label: customLabel }] : options;
  const [active, setActive] = useState(0);
  const wrap = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const current = options.find((o) => o.value === value);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    list.current?.focus();
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const openList = () => {
    setActive(Math.max(0, all.findIndex((o) => o.value === value)));
    setOpen(true);
  };

  const choose = (v: string) => {
    setOpen(false);
    if (v === CUSTOM) {
      setCustomValue('');
      setCustom(true);
      return;
    }
    onChange(v);
    button.current?.focus();
  };

  const onListKey = (e: KeyboardEvent) => {
    if (e.key === 'ArrowDown') setActive((a) => Math.min(all.length - 1, a + 1));
    else if (e.key === 'ArrowUp') setActive((a) => Math.max(0, a - 1));
    else if (e.key === 'Home') setActive(0);
    else if (e.key === 'End') setActive(all.length - 1);
    else if (e.key === 'Enter' || e.key === ' ') choose(all[active].value);
    else if (e.key === 'Escape' || e.key === 'Tab') {
      setOpen(false);
      if (e.key === 'Escape') button.current?.focus();
      return;
    } else return;
    e.preventDefault();
  };

  if (custom) {
    return (
      <div className="dropdown" style={{ width }}>
        <input
          autoFocus
          className="input input--inline"
          style={{ height: variant === 'field' ? 44 : 36 }}
          aria-label={label}
          placeholder={customPlaceholder}
          value={customValue}
          onChange={(e) => setCustomValue(e.target.value)}
          onBlur={() => {
            if (customValue.trim()) onChange(customValue.trim());
            setCustom(false);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') (e.target as HTMLInputElement).blur();
            if (e.key === 'Escape') {
              setCustomValue('');
              setCustom(false);
            }
          }}
        />
      </div>
    );
  }

  return (
    <div className="dropdown" ref={wrap} style={{ width }}>
      <button
        ref={button}
        type="button"
        className={`dropdown__button${variant === 'field' ? ' dropdown__button--field' : ''}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={labelledBy ? undefined : `${label}: ${current?.label ?? value}`}
        aria-labelledby={labelledBy ? `${labelledBy} ${id}-value` : undefined}
        disabled={disabled}
        title={disabled ? disabledReason : undefined}
        onClick={() => (open ? setOpen(false) : openList())}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            openList();
          }
        }}
      >
        <span id={`${id}-value`} className="truncate">
          {current?.label ?? value}
        </span>
        <CaretDownIcon size={16} aria-hidden />
      </button>
      {open && (
        <ul
          ref={list}
          role="listbox"
          tabIndex={-1}
          aria-label={label}
          aria-activedescendant={`${id}-opt-${active}`}
          className="dropdown__list"
          onKeyDown={onListKey}
        >
          {all.map((o, i) => (
            <li
              key={o.value}
              id={`${id}-opt-${i}`}
              role="option"
              aria-selected={o.value === value}
              className={`dropdown__option${i === active ? ' is-active' : ''}${o.value === CUSTOM ? ' dropdown__option--muted' : ''}`}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => choose(o.value)}
            >
              <span>{o.label}</span>
              {o.value === value && <CheckIcon size={16} aria-hidden />}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
