import { CheckIcon, PencilSimpleIcon, TrashIcon } from '@phosphor-icons/react';
import { Fragment, useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { useI18n } from '../i18n/I18nProvider';
import { alternativesFor, lineTokens } from '../lib/transcript';
import type { Task, TranscriptLine, TranscriptToken } from '../types';

/** Read-only token rendering (history record, dialogs). */
function StaticTokens({ tokens }: { tokens: TranscriptToken[] }) {
  return (
    <>
      {tokens.map((tok, i) =>
        tok.kind === 'kw' ? (
          <mark key={i} className="kw">
            {tok.text}
          </mark>
        ) : (
          <Fragment key={i}>{tok.text}</Fragment>
        ),
      )}
    </>
  );
}

interface MenuState {
  line: number;
  token: number;
  anchor: DOMRect;
}

/** Popover to pick an alternative reading or type the right word. */
function WordMenu({ word, alternatives, anchor, onPick, onRemove, onClose }: { word: string; alternatives: string[]; anchor: DOMRect; onPick: (v: string) => void; onRemove?: () => void; onClose: () => void }) {
  const { t } = useI18n();
  const id = useId();
  const box = useRef<HTMLDivElement>(null);
  const [editing, setEditing] = useState(alternatives.length === 0);
  const [value, setValue] = useState(word);
  const [pos, setPos] = useState({ top: anchor.bottom + 6, left: anchor.left });

  // Keep inside the viewport; flip above the word if there's no room below.
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    const top = anchor.bottom + 6 + height > innerHeight - 8 ? anchor.top - 6 - height : anchor.bottom + 6;
    setPos({ top, left: Math.min(anchor.left, innerWidth - width - 8) });
  }, [anchor, editing]);

  useEffect(() => {
    const first = box.current?.querySelector<HTMLElement>('input, [role=menuitem]');
    first?.focus();
    const onDown = (e: MouseEvent) => !box.current?.contains(e.target as Node) && onClose();
    const onScroll = (e: Event) => !box.current?.contains(e.target as Node) && onClose();
    document.addEventListener('mousedown', onDown);
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', onClose);
    return () => {
      document.removeEventListener('mousedown', onDown);
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', onClose);
    };
  }, [editing, onClose]);

  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Escape') return (e.stopPropagation(), onClose());
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    const items = Array.from(box.current?.querySelectorAll<HTMLElement>('[role=menuitem]') ?? []);
    const i = items.indexOf(document.activeElement as HTMLElement);
    items[(i + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length]?.focus();
    e.preventDefault();
  };

  return createPortal(
    <div ref={box} className="word-menu" style={pos} role="menu" aria-labelledby={`${id}-h`} onKeyDown={onKey}>
      <p id={`${id}-h`} className="word-menu__head t-plate c-secondary">
        {alternatives.length ? t('review.word.didYouMean') : t('review.word.fix')}
      </p>
      {!editing && (
        <>
          <button type="button" role="menuitem" className="dropdown__option word-menu__item" aria-current="true" onClick={onClose}>
            <span>{word}</span>
            <CheckIcon size={16} aria-hidden />
          </button>
          {alternatives.map((a) => (
            <button key={a} type="button" role="menuitem" className="dropdown__option word-menu__item" onClick={() => onPick(a)}>
              {a}
            </button>
          ))}
          <button type="button" role="menuitem" className="dropdown__option word-menu__item dropdown__option--muted" onClick={() => setEditing(true)}>
            <span>{t('review.word.edit')}</span>
            <PencilSimpleIcon size={16} aria-hidden />
          </button>
        </>
      )}
      {editing && (
        <form
          className="word-menu__edit"
          onSubmit={(e) => {
            e.preventDefault();
            const v = value.trim();
            if (v && v !== word) onPick(v);
            else onClose();
          }}
        >
          <input className="input input--inline" aria-label={t('review.word.fix')} value={value} onChange={(e) => setValue(e.target.value)} onFocus={(e) => e.target.select()} />
          <button type="submit" className="btn btn--primary word-menu__save">
            {t('review.word.save')}
          </button>
        </form>
      )}
      {/* Offered in both views: pick-a-reading and type-it-yourself. */}
      {onRemove && (
        <button type="button" role="menuitem" className="dropdown__option word-menu__item word-menu__remove" onClick={onRemove}>
          <span>{t('review.word.remove')}</span>
          <TrashIcon size={16} aria-hidden />
        </button>
      )}
    </div>,
    document.body,
  );
}

interface LinesProps {
  lines: TranscriptLine[];
  nameOf: (id: string) => string;
  /** When set, every word/term is clickable and can be corrected. */
  onCorrect?: (line: number, token: number, value: string) => void;
  /** When set, the word menu also offers "Remove word". */
  onRemove?: (line: number, token: number) => void;
}

export function TranscriptLines({ lines, nameOf, onCorrect, onRemove }: LinesProps) {
  const { t } = useI18n();
  const [menu, setMenu] = useState<MenuState | null>(null);
  const root = useRef<HTMLOListElement>(null);
  const lastFocus = useRef<HTMLElement | null>(null);

  const close = () => {
    setMenu(null);
    lastFocus.current?.focus();
  };

  // ← → move between words; the list is otherwise one tab stop per flagged word/term.
  const onWordKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    const words = Array.from(root.current?.querySelectorAll<HTMLButtonElement>('.word') ?? []);
    const i = words.indexOf(e.currentTarget);
    words[i + (e.key === 'ArrowRight' ? 1 : -1)]?.focus();
    e.preventDefault();
  };

  const menuTokens = menu ? lineTokens(lines[menu.line]) : [];
  const menuWord = menu ? menuTokens[menu.token]?.text ?? '' : '';

  return (
    <>
      <ol className="transcript" ref={root}>
        {lines.map((l, li) => (
          <li key={li} className="transcript__line">
            <p className="row">
              <span className="t-data-sm c-secondary">{l.at}</span>
              <span className="t-strong">{nameOf(l.speakerId)}</span>
            </p>
            <p className="t-body-md transcript__text">
              {!onCorrect ? (
                <StaticTokens tokens={lineTokens(l)} />
              ) : (
                lineTokens(l).map((tok, ti) => {
                  if (tok.kind === 'space' || tok.kind === 'punct') return <Fragment key={ti}>{tok.text}</Fragment>;
                  const unsure = !tok.fixed && alternativesFor(tok.text).length > 0;
                  const cls = ['word', tok.kind === 'kw' && 'kw', unsure && 'word--unsure', tok.fixed && 'word--fixed'].filter(Boolean).join(' ');
                  return (
                    <button
                      key={ti}
                      type="button"
                      className={cls}
                      tabIndex={unsure || tok.kind === 'kw' ? 0 : -1}
                      aria-haspopup="menu"
                      aria-expanded={menu?.line === li && menu.token === ti}
                      aria-label={t(unsure ? 'review.word.labelUnsure' : tok.fixed ? 'review.word.labelFixed' : 'review.word.label', { word: tok.text })}
                      onKeyDown={onWordKey}
                      onClick={(e) => {
                        lastFocus.current = e.currentTarget;
                        setMenu({ line: li, token: ti, anchor: e.currentTarget.getBoundingClientRect() });
                      }}
                    >
                      {tok.text}
                    </button>
                  );
                })
              )}
            </p>
          </li>
        ))}
      </ol>
      {menu && onCorrect && (
        <WordMenu
          key={`${menu.line}-${menu.token}`}
          word={menuWord}
          alternatives={alternativesFor(menuWord)}
          anchor={menu.anchor}
          onClose={close}
          onPick={(v) => {
            onCorrect(menu.line, menu.token, v);
            close();
          }}
          onRemove={
            onRemove &&
            (() => {
              onRemove(menu.line, menu.token);
              setMenu(null);
              // The word's button is gone; keep keyboard users in the transcript.
              root.current?.querySelector<HTMLElement>('.word[tabindex="0"]')?.focus();
            })
          }
        />
      )}
    </>
  );
}

/** Group tasks owner → patient, keeping first-seen order; tasks sorted by due date. */
export function groupTasks(tasks: Task[]) {
  const owners: { ownerId: string; patients: { patient: string; tasks: Task[] }[] }[] = [];
  for (const task of tasks) {
    let o = owners.find((x) => x.ownerId === task.ownerId);
    if (!o) owners.push((o = { ownerId: task.ownerId, patients: [] }));
    let p = o.patients.find((x) => x.patient === task.patient);
    if (!p) o.patients.push((p = { patient: task.patient, tasks: [] }));
    p.tasks.push(task);
  }
  for (const o of owners) for (const p of o.patients) p.tasks.sort((a, b) => a.due.localeCompare(b.due));
  return owners;
}
