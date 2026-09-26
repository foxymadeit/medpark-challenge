import { PencilSimpleIcon } from '@phosphor-icons/react';
import { useId, useRef, type InputHTMLAttributes } from 'react';

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  label: string;
  error?: string;
  /** Shows a pen at the end of the field: the shared "you can edit this" cue. */
  editable?: boolean;
}

/** Label + 48px input + optional error line (Figma "Input field"). */
export function TextField({ label, error, editable, className = '', ...rest }: Props) {
  const id = useId();
  const errId = `${id}-err`;
  const input = useRef<HTMLInputElement>(null);
  const field = (
    <input ref={input} id={id} className="input" aria-invalid={error ? true : undefined} aria-describedby={error ? errId : undefined} {...rest} />
  );
  return (
    <div className={`field ${className}`.trim()}>
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      {editable ? (
        <span className="input-wrap">
          {field}
          <PencilSimpleIcon size={16} aria-hidden className="input-wrap__pen" onClick={() => input.current?.focus()} />
        </span>
      ) : (
        field
      )}
      {error && (
        <p id={errId} className="field__error">
          {error}
        </p>
      )}
    </div>
  );
}
