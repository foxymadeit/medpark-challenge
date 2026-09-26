import { useId, type InputHTMLAttributes } from 'react';

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  label: string;
  error?: string;
}

/** Label + 48px input + optional error line (Figma "Input field"). */
export function TextField({ label, error, className = '', ...rest }: Props) {
  const id = useId();
  const errId = `${id}-err`;
  return (
    <div className={`field ${className}`.trim()}>
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className="input"
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errId : undefined}
        {...rest}
      />
      {error && (
        <p id={errId} className="field__error">
          {error}
        </p>
      )}
    </div>
  );
}
