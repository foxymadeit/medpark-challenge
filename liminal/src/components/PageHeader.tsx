import type { ReactNode } from 'react';

/**
 * The top of every section page (New meeting, Participants, Templates, History, Settings), on one grid:
 * optional small label (y 88), title (y 112, Onest 28/36), optional thing on the right (a button, the date…),
 * and 20px below it the page's first block (y 168). The label's line is kept even when there's no label,
 * so titles never jump between sections. `title` is a string (an h1 is made) or the page's own headline node.
 */
export function PageHeader({ eyebrow, title, aside, className = '' }: { eyebrow?: ReactNode; title: ReactNode; aside?: ReactNode; className?: string }) {
  return (
    <header className={`page-header ${className}`.trim()}>
      <div className="page-header__main">
        <p className="page-header__eyebrow">{eyebrow}</p>
        {typeof title === 'string' ? <h1 className="t-h1 page-header__title">{title}</h1> : title}
      </div>
      {aside}
    </header>
  );
}
