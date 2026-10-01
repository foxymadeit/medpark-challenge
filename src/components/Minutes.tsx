import { CheckIcon, PencilSimpleIcon, PlayIcon, StopIcon, TrashIcon, XIcon } from '@phosphor-icons/react';
import { Fragment, useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { useI18n } from '../i18n/I18nProvider';
import { Avatar } from './Avatar';
import { alternativesFor, lineSeconds, lineText, lineTokens, originalText } from '../lib/transcript';
import { SPOKEN_LANGS, type SpokenLang, type Task, type TranscriptLine, type TranscriptToken } from '../types';

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
function WordMenu({ word, alternatives, anchor, onPick, onRemove, lang, onLang, onClose }: { word: string; alternatives: string[]; anchor: DOMRect; onPick: (v: string) => void; onRemove?: () => void; lang?: SpokenLang; onLang?: (l: SpokenLang | undefined) => void; onClose: () => void }) {
  const { t } = useI18n();
  const id = useId();
  const box = useRef<HTMLDivElement>(null);
  const [editing, setEditing] = useState(alternatives.length === 0);
  const [value, setValue] = useState(word);
  // The language flag is staged too: nothing is stored until Save.
  const [pickedLang, setPickedLang] = useState(lang);
  const wordChanged = editing && !!value.trim() && value.trim() !== word;
  const langChanged = pickedLang !== lang;
  const dirty = wordChanged || langChanged;
  const save = () => {
    if (langChanged) onLang?.(pickedLang);
    if (wordChanged) onPick(value.trim());
    else onClose();
  };
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
            save();
          }}
        >
          {/* The shared pen cue; kept visible here since the field opens already focused. */}
          <span className="input-wrap word-menu__field">
            <input className="input input--inline" aria-label={t('review.word.fix')} value={value} onChange={(e) => setValue(e.target.value)} onFocus={(e) => e.target.select()} />
            <PencilSimpleIcon size={16} aria-hidden className="input-wrap__pen" />
          </span>
          {/* Only once the word or its language differs; Enter with no change just closes. */}
          {dirty && (
            <button type="submit" className="btn btn--ink word-menu__save">
              {t('review.word.save')}
            </button>
          )}
        </form>
      )}
      {/* Language flag: which language this word really is (training label). Click again to clear. */}
      {onLang && (
        <div className="word-menu__lang">
          <span className="word-menu__lang-label">{t('review.word.langLabel')}</span>
          {/* Same look as the interface-language switch in the top bar. */}
          <div className="segmented segmented--lang" role="radiogroup" aria-label={t('review.word.langLabel')}>
            {SPOKEN_LANGS.map((l) => (
              <button key={l} type="button" role="radio" aria-checked={pickedLang === l} className="segmented__item" title={t(`spoken.${l}`)} onClick={() => setPickedLang(pickedLang === l ? undefined : l)}>
                {l.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      )}
      {/* Not typing a new word: the Save for a language change sits under the switch. */}
      {!editing && langChanged && (
        <div className="word-menu__actions">
          <button type="button" className="btn btn--ink word-menu__save" onClick={save}>
            {t('review.word.save')}
          </button>
        </div>
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
  /** When set, the word menu lets the reviewer flag the word's language. */
  onFlagLang?: (line: number, token: number, lang: SpokenLang | undefined) => void;
  /** When set, a sentence can be selected (click its time/speaker) to listen, rewrite or remove it. */
  onEditLine?: (line: number, text: string) => void;
  onRemoveLine?: (line: number) => void;
}

/**
 * MOCK audio: plays the segment's length with a progress bar and reads what the AI originally heard
 * with the browser's speech voice, so it can be compared with the corrected text. A real build plays
 * the recording between this line's timestamp and the next.
 */
function useSegmentPlayer() {
  const [playing, setPlaying] = useState<number | null>(null);
  const [progress, setProgress] = useState(0);
  const timer = useRef<number | undefined>(undefined);
  const stop = () => {
    window.clearInterval(timer.current);
    window.speechSynthesis?.cancel();
    setPlaying(null);
    setProgress(0);
  };
  const play = (i: number, seconds: number, text: string, lang: string) => {
    stop();
    setPlaying(i);
    const started = performance.now();
    timer.current = window.setInterval(() => {
      const p = (performance.now() - started) / (seconds * 1000);
      if (p >= 1) stop();
      else setProgress(p);
    }, 100);
    if ('speechSynthesis' in window) {
      const u = new SpeechSynthesisUtterance(text);
      u.lang = lang;
      window.speechSynthesis.speak(u);
    }
  };
  useEffect(() => stop, []); // stop on unmount
  return { playing, progress, play, stop };
}


/** Speaker's colour circle in the transcript: same colour as their avatar everywhere; unknown voices stay neutral grey. */
function SpeakerAvatar({ id, name }: { id: string; name: string }) {
  return <Avatar name={name} size="sm" color={id.startsWith('voice-') ? 'stone' : undefined} />;
}
export function TranscriptLines({ lines, nameOf, onCorrect, onRemove, onFlagLang, onEditLine, onRemoveLine }: LinesProps) {
  const { lang } = useI18n();
  const [selected, setSelected] = useState<number | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState('');
  const player = useSegmentPlayer();
  const sentences = !!(onEditLine || onRemoveLine);
  const select = (i: number) => {
    player.stop();
    setEditing(null);
    setSelected((s) => (s === i ? null : i));
  };
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
          <li key={li} className={`transcript__line${selected === li ? ' is-selected' : ''}`}>
            {sentences ? (
              <button type="button" className="transcript__head" aria-pressed={selected === li} aria-label={t('review.sentence.select', { time: l.at, name: nameOf(l.speakerId) })} onClick={() => select(li)}>
                <SpeakerAvatar id={l.speakerId} name={nameOf(l.speakerId)} />
                <span className="t-strong">{nameOf(l.speakerId)}</span>
                <span className="t-data-sm c-secondary">{l.at}</span>
                {l.edited && <span className="tag transcript__edited">{t('review.sentence.edited')}</span>}
              </button>
            ) : (
              <p className="row">
                <SpeakerAvatar id={l.speakerId} name={nameOf(l.speakerId)} />
                <span className="t-strong">{nameOf(l.speakerId)}</span>
                <span className="t-data-sm c-secondary">{l.at}</span>
              </p>
            )}
            {editing === li ? (
              <form
                className="sentence-edit"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (draft.trim() && draft.trim() !== lineText(l)) onEditLine?.(li, draft.trim());
                  setEditing(null);
                }}
              >
                <textarea className="input sentence-edit__input" aria-label={t('review.sentence.edit')} value={draft} autoFocus rows={3} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => e.key === 'Escape' && (e.stopPropagation(), setEditing(null))} />
                <div className="row" style={{ gap: 8, justifyContent: 'flex-end' }}>
                  <button type="button" className="btn btn--ghost" onClick={() => setEditing(null)}>
                    {t('common.cancel')}
                  </button>
                  {/* Save shows only once the sentence actually changed. */}
                  {draft.trim() && draft.trim() !== lineText(l) && (
                    <button type="submit" className="btn btn--primary">
                      <CheckIcon size={16} aria-hidden />
                      {t('common.save')}
                    </button>
                  )}
                </div>
              </form>
            ) : null}
            {editing !== li && <p className="t-body-md transcript__text">
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
                      {tok.lang && <span className="word__lang">{tok.lang.toUpperCase()}</span>}
                    </button>
                  );
                })
              )}
            </p>}
            {/* Pen at the line's right end while hovering its words: one click edits the whole sentence. */}
            {onEditLine && editing !== li && (
              <button
                type="button"
                className="icon-btn edit-btn transcript__pen"
                aria-label={t('review.sentence.edit')}
                title={t('review.sentence.edit')}
                onClick={() => (player.stop(), setSelected(li), setDraft(lineText(l)), setEditing(li))}
              >
                <PencilSimpleIcon size={16} aria-hidden />
              </button>
            )}
            {sentences && selected === li && editing !== li && (
              <div className="sentence-actions" role="group" aria-label={t('review.sentence.actions')}>
                <button
                  type="button"
                  className="btn btn--secondary sentence-actions__btn"
                  aria-pressed={player.playing === li}
                  onClick={() => (player.playing === li ? player.stop() : player.play(li, lineSeconds(lines, li), originalText(l), lang === 'en' ? 'en-US' : lang === 'ro' ? 'ro-RO' : 'ru-RU'))}
                >
                  {player.playing === li ? <StopIcon size={16} aria-hidden /> : <PlayIcon size={16} aria-hidden />}
                  {player.playing === li ? t('review.sentence.stop') : t('review.sentence.listen')}
                </button>
                {onEditLine && (
                  <button type="button" className="btn btn--ghost sentence-actions__btn" onClick={() => (player.stop(), setDraft(lineText(l)), setEditing(li))}>
                    <PencilSimpleIcon size={16} aria-hidden />
                    {t('review.sentence.edit')}
                  </button>
                )}
                {onRemoveLine && (
                  <button type="button" className="btn btn--ghost sentence-actions__btn sentence-actions__remove" onClick={() => (player.stop(), setSelected(null), onRemoveLine(li))}>
                    <TrashIcon size={16} aria-hidden />
                    {t('review.sentence.remove')}
                  </button>
                )}
                <button type="button" className="icon-btn sentence-actions__close" aria-label={t('common.close')} onClick={() => select(li)}>
                  <XIcon size={16} aria-hidden />
                </button>
                {player.playing === li && (
                  <div className="sentence-player">
                    <div className="sentence-player__bar">
                      <div className="sentence-player__fill" style={{ width: `${player.progress * 100}%` }} />
                    </div>
                    <span className="note">{t('review.sentence.heard', { text: originalText(l) })}</span>
                  </div>
                )}
              </div>
            )}
          </li>
        ))}
      </ol>
      {menu && onCorrect && (
        <WordMenu
          key={`${menu.line}-${menu.token}`}
          word={menuWord}
          lang={menuTokens[menu.token]?.lang}
          onLang={onFlagLang && ((l) => onFlagLang(menu.line, menu.token, l))}
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
