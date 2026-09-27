import { XIcon } from '@phosphor-icons/react';
import { useEffect, useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useI18n } from '../i18n/I18nProvider';

interface Props {
  title: string;
  onClose: () => void;
  children: ReactNode;
  variant?: 'modal' | 'panel';
  wide?: boolean;
  /** Extra class on the dialog box (e.g. a size). */
  className?: string;
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])';

/** Modal (centered) or side panel (right). Esc / scrim click closes, focus is trapped and restored. */
export function Dialog({ title, onClose, children, variant = 'modal', wide, className = '' }: Props) {
  const { t } = useI18n();
  const titleId = useId();
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const first = box.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
    // Focus the first form control if there is one, else the close button.
    const target = Array.from(first ?? []).find((el) => el.tagName === 'INPUT') ?? first?.[0];
    target?.focus();
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
      previous?.focus();
    };
  }, []);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      onClose();
      return;
    }
    if (e.key !== 'Tab' || !box.current) return;
    const items = Array.from(box.current.querySelectorAll<HTMLElement>(FOCUSABLE));
    if (!items.length) return;
    const [firstEl, lastEl] = [items[0], items[items.length - 1]];
    if (e.shiftKey && document.activeElement === firstEl) {
      e.preventDefault();
      lastEl.focus();
    } else if (!e.shiftKey && document.activeElement === lastEl) {
      e.preventDefault();
      firstEl.focus();
    }
  };

  return createPortal(
    <div className={`scrim${variant === 'panel' ? ' scrim--right' : ''}`} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={box}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`${variant === 'panel' ? 'side-panel' : `modal${wide ? ' modal--wide' : ''}`} ${className}`.trim()}
        onKeyDown={onKeyDown}
      >
        <div className="dialog-head">
          <h2 id={titleId} className="t-h2">
            {title}
          </h2>
          <button type="button" className="icon-btn" aria-label={t('common.close')} onClick={onClose}>
            <XIcon size={20} aria-hidden />
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}
