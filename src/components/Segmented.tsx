import { useRef, type KeyboardEvent } from 'react';

interface Option<T extends string> {
  value: T;
  label: string;
}

interface Props<T extends string> {
  label: string;
  options: Option<T>[];
  value: T;
  onChange: (value: T) => void;
  /** fill = stretch to the row; auto = items size to their label; lang = compact top-bar switch. */
  variant?: 'default' | 'fill' | 'auto' | 'lang';
}

/** Radio-group segmented control with roving tabindex and arrow-key navigation. */
export function Segmented<T extends string>({ label, options, value, onChange, variant = 'default' }: Props<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const move = (e: KeyboardEvent, index: number) => {
    const delta = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
    if (!delta) return;
    e.preventDefault();
    const next = (index + delta + options.length) % options.length;
    onChange(options[next].value);
    refs.current[next]?.focus();
  };

  return (
    <div role="radiogroup" aria-label={label} className={`segmented${variant !== 'default' ? ` segmented--${variant}` : ''}`}>
      {options.map((o, i) => {
        const checked = o.value === value;
        return (
          <button
            key={o.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={checked ? 0 : -1}
            className="segmented__item"
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => move(e, i)}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
