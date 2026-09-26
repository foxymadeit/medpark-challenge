import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Variant = 'primary' | 'ink' | 'secondary' | 'ghost' | 'danger';

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  icon?: ReactNode;
  block?: boolean;
}

export function Button({ variant = 'secondary', icon, block, className = '', children, type = 'button', ...rest }: Props) {
  return (
    <button type={type} className={`btn btn--${variant}${block ? ' btn--block' : ''} ${className}`.trim()} {...rest}>
      {icon}
      {children}
    </button>
  );
}
