import { DownloadSimpleIcon, PaperPlaneTiltIcon, PencilSimpleIcon, PlusIcon } from '@phosphor-icons/react';
import { useLayoutEffect, useRef, useState, type TextareaHTMLAttributes } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { Avatar } from '../components/Avatar';
import { Button } from '../components/Button';
import { DatePicker } from '../components/DatePicker';
import { SummaryText } from '../components/SummaryText';
import { Dialog } from '../components/Dialog';
import { MomPreview } from '../components/MomPreview';
import { Dropdown } from '../components/Dropdown';
import { TranscriptLines } from '../components/Minutes';
import { OwnerPicker } from '../components/OwnerPicker';
import { ParticipantsPanel } from '../components/ParticipantsPanel';
import { Segmented } from '../components/Segmented';
import { useI18n } from '../i18n/I18nProvider';
import { addDays, daysBetween, DUE_OFFSETS, dueRelative, formatWeekdayDate, todayISO, uid } from '../lib/format';
import { speakers } from '../lib/meeting';
import { downloadMomPdf } from '../lib/momPdf';
import { useStore } from '../store/AppStore';
import type { Meeting, ParticipantSnapshot, Task } from '../types';

/** Task text edited in place: wraps and grows like the read-mode text (same font, no padding), Enter saves. */
function InlineText(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = '0';
    el.style.height = `${el.scrollHeight}px`;
  });
  return <textarea ref={ref} rows={1} {...props} />;
}

/** Deadline as said in the meeting ("Tomorrow", "In 3 days"…) plus the date it resolves to. */
function useDueLabel(meetingDate: string) {
  const { t, lang } = useI18n();
  return (iso: string) => {
    const rel = dueRelative(meetingDate, iso);
    const date = formatWeekdayDate(iso, lang);
    return { rel: rel ? t(rel.key, rel.vars) : date, date: rel ? date : '' };
  };
}

/** Meeting name, renamed as on New meeting: click it or its pen, the field opens on the same line in the same type with
 * the name selected; Enter or leaving it saves, Esc cancels. */
const HEADLINE_PEN_ROOM = 40; // the pen and its gap after the name
const HEAD_GAPS = 40; // name to date 16, date to view switch 24

function EditableTitle({ meeting }: { meeting: Meeting }) {
  const { t } = useI18n();
  const { updateMeeting } = useStore();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(meeting.title);
  const start = () => (setValue(meeting.title), setEditing(true));
  const commit = () => {
    if (value.trim()) updateMeeting(meeting.id, { title: value.trim() });
    setEditing(false);
  };
  if (editing)
    return (
      <input
        autoFocus
        className="input headline-input"
        aria-label={t('review.titleLabel')}
        value={value}
        maxLength={120}
        onChange={(e) => setValue(e.target.value)}
        onFocus={(e) => e.target.select()}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit();
          if (e.key === 'Escape') setEditing(false);
        }}
      />
    );
  return (
    <div className="headline">
      <h1 className="t-h1 headline__text review__title" onClick={start}>
        {meeting.title}
      </h1>
      <button type="button" className="icon-btn edit-btn headline__pen" aria-label={t('review.renameLabel')} title={t('review.renameLabel')} onClick={start}>
        <PencilSimpleIcon size={20} aria-hidden />
      </button>
    </div>
  );
}

/** Do the name and meta line, the date and the view switch fit on one row? Hidden `.fit-probe` copies give the name and meta
 * their full width, which differs per language and meeting, so a breakpoint can't decide it. Only used from 641 up. */
function useHeadFits(title: string, meta: string) {
  const head = useRef<HTMLElement>(null);
  const [fits, setFits] = useState(true);

  useLayoutEffect(() => {
    const el = head.current;
    if (!el) return;
    const width = (selector: string) => el.querySelector(selector)?.getBoundingClientRect().width ?? 0;
    const measure = () => {
      const text = Math.max(width('.review__fit-title') + HEADLINE_PEN_ROOM, width('.review__fit-meta'));
      setFits(text + width('.datepicker') + width('.segmented') + HEAD_GAPS <= el.clientWidth);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    void document.fonts.ready.then(measure); // the probes are narrower in the fallback font
    return () => observer.disconnect();
  }, [title, meta]);

  return { head, fits };
}

/** 05 — Review the AI minutes, then send (Figma "05 MoM · D4 B"). One white card with one scroll: Summary (at most half
 * the card), then Tasks under a sticky header; confirm every task. Participants (= who gets the MoM) in a panel on the
 * right. Preview / Send under the card, centred on the window. Transcript tab: read-only, in the same card. */
export function Review() {
  const { t, lang } = useI18n();
  const { id } = useParams();
  const navigate = useNavigate();
  const { account, meetings, setTasks, setSummary, sendMeeting, resolvePerson, updateMeeting } = useStore();
  const meeting = meetings.find((m) => m.id === id);
  const [row, setRow] = useState<Task | null>(null); // the task being edited (or added)
  const [tab, setTab] = useState<'mom' | 'transcript'>('mom'); // MoM first
  const [previewOpen, setPreviewOpen] = useState(false); // MoM text preview popup
  const dueLabel = useDueLabel(meeting?.date ?? '');
  const meta = meeting ? t('review.meta', { type: t(`types.${meeting.type}`), n: meeting.durationMin, count: meeting.participants.length }) : '';
  const { head, fits } = useHeadFits(meeting?.title ?? '', meta);

  const sent = useRef(false);
  const send = () => {
    if (!meeting || sent.current) return;
    sent.current = true;
    sendMeeting(meeting.id);
    navigate(`/sent/${meeting.id}`);
  };

  if (!meeting) return <Navigate to="/history" replace />;
  // After our own send(), navigation to /sent is in flight (router uses transitions) — don't redirect.
  if (meeting.status === 'sent' && !sent.current) return <Navigate to={`/history/${meeting.id}`} replace />;
  if (meeting.status === 'processing') return <Navigate to={`/processing/${meeting.id}`} replace />;

  const { nameOf, badgeOf } = speakers(meeting, resolvePerson, t); // badgeOf: an unknown voice as owner, "S1" on its colour
  const tasks = [...meeting.tasks].sort((a, b) => a.due.localeCompare(b.due));
  const dueOptions = [...new Set([...DUE_OFFSETS.map((n) => addDays(meeting.date, n)), ...(row ? [row.due] : [])])].sort();
  // Send is on only when every action item is confirmed. Confirm per row (the row checkbox), or all at once with the
  // footer checkbox, which also takes them all back.
  const confirmed = meeting.tasks.filter((x) => x.confirmed).length;
  const allConfirmed = confirmed === meeting.tasks.length;
  const someConfirmed = confirmed > 0 && !allConfirmed;
  const toggleConfirm = (task: Task) => setTasks(meeting.id, meeting.tasks.map((x) => (x.id === task.id ? { ...x, confirmed: !x.confirmed } : x)));
  const setAllConfirmed = (on: boolean) => setTasks(meeting.id, meeting.tasks.map((x) => ({ ...x, confirmed: on })));
  const setParticipants = (participants: ParticipantSnapshot[]) => updateMeeting(meeting.id, { participants });
  // A new meeting date moves the deadlines with it, so "Tomorrow" stays tomorrow.
  const changeDate = (date: string) => {
    const shift = daysBetween(meeting.date, date);
    updateMeeting(meeting.id, { date, tasks: meeting.tasks.map((x) => ({ ...x, due: addDays(x.due, shift) })) });
    if (row) setRow({ ...row, due: addDays(row.due, shift) });
  };

  const isNew = !!row && !meeting.tasks.some((x) => x.id === row.id);
  // A new task shows as an editing row on top; it's only added once saved.
  const rows = isNew && row ? [row, ...tasks] : tasks;
  const addTask = () =>
    setRow({ id: uid('task'), ownerId: account?.personId && meeting.participants.some((p) => p.personId === account.personId) ? account.personId : meeting.participants[0]?.personId ?? '', patient: '', title: '', due: addDays(meeting.date, 1) });
  const cancelRow = () => setRow(null);
  const saveRow = () => {
    if (row && row.title.trim()) {
      // An edited (or new) action item, owner included, needs confirming again.
      const clean = { ...row, title: row.title.trim(), patient: row.patient.trim(), confirmed: false };
      setTasks(meeting.id, isNew ? [...meeting.tasks, clean] : meeting.tasks.map((x) => (x.id === row.id ? clean : x)));
    }
    cancelRow();
  };
  // Owner picked while editing: kept with the row until Save; someone new joins the meeting right away.
  const pickOwner = (owner: ParticipantSnapshot) => {
    if (!meeting.participants.some((p) => p.personId === owner.personId)) setParticipants([...meeting.participants, owner]);
    if (row) setRow({ ...row, ownerId: owner.personId });
  };
  const sendBlocked = allConfirmed ? undefined : t('review.confirmAllFirst');

  return (
    <div className="page review page--fit">
      <div className="review__layout">
        <header ref={head} className={`review__header${fits ? '' : ' review__header--stacked'}`}>
          <span className="fit-probe t-h1 review__fit-title" aria-hidden>{meeting.title}</span>
          <span className="fit-probe note review__fit-meta" aria-hidden>{meta}</span>
          {/* Name and date in two columns, as on New meeting. */}
          <div className="review__head-main">
            <div className="stack review__head-text" style={{ gap: 'var(--sm-space-1)' }}>
              <EditableTitle meeting={meeting} />
              <p className="note">{meta}</p>
            </div>
            <DatePicker label={t('newMeeting.date')} max={todayISO()} value={meeting.date} onChange={changeDate} />
          </div>
          <Segmented<'mom' | 'transcript'>
            label={t('review.view')}
            variant="auto"
            value={tab}
            onChange={setTab}
            options={[
              { value: 'mom', label: t('review.tabMom') },
              { value: 'transcript', label: t('review.transcript') },
            ]}
          />
        </header>

        <section className="card review__card" aria-label={tab === 'mom' ? t('review.tabMom') : t('review.transcript')}>
          {tab === 'mom' ? (
            <div className="review__scroll">
              {/* Summary: at most half the card; a longer one scrolls inside. */}
              <section className="review__summary" aria-labelledby="rv-summary">
                <SummaryText
                  points={meeting.summary ?? []}
                  onChange={(points) => setSummary(meeting.id, points)}
                  head={
                    <h2 id="rv-summary" className="review__pane-title">
                      {t('review.summary')}
                    </h2>
                  }
                />
              </section>

              {/* Tasks: one header row (title, count, Owner, Deadline, Add task), sticky while the card scrolls. */}
              <table className="summary-table task-table" aria-label={t('review.tasks')}>
                <thead>
                  <tr>
                    <th scope="col">
                      <span className="review__count-head">
                        <span className="review__pane-title">{t('review.tasks')}</span>
                        <span className="note">{meeting.tasks.length}</span>
                      </span>
                    </th>
                    <th scope="col">{t('review.owner')}</th>
                    <th scope="col">{t('review.due')}</th>
                    <th scope="col">
                      <span className="sr-only">{t('review.actions')}</span>
                      <button type="button" className="note add-link" onClick={addTask} disabled={!!row}>
                        <PlusIcon size={16} aria-hidden />
                        {t('review.addTask')}
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((task) =>
                    row && row.id === task.id ? (
                      <tr key={task.id} className="is-editing" onKeyDown={(e) => e.key === 'Escape' && (e.stopPropagation(), cancelRow())}>
                        {/* Edit: same columns as reading; the row lights up across the card, the texts become fields. */}
                        <td>
                          {/* The checkbox stays, inactive, so the fields keep the read-mode text's spot. */}
                          <div className="task-check">
                            <input type="checkbox" className="checkbox" checked={false} disabled readOnly aria-hidden />
                            <div className="task-check__text">
                              {/* A textarea like the task's, not an input: browsers place an input's text on their own, and it would jump. */}
                              <InlineText className="task-edit summary-table__patient" aria-label={t('review.patientField')} placeholder={t('review.patientField')} value={row.patient} onChange={(e) => setRow({ ...row, patient: e.target.value })} onKeyDown={(e) => (e.key === 'Enter' ? (e.preventDefault(), saveRow()) : e.key === 'Escape' ? cancelRow() : undefined)} />
                              <InlineText className="task-edit task-table__title" aria-label={t('review.task')} placeholder={t('review.taskPh')} value={row.title} autoFocus onChange={(e) => setRow({ ...row, title: e.target.value })} onKeyDown={(e) => (e.key === 'Enter' ? (e.preventDefault(), saveRow()) : e.key === 'Escape' ? cancelRow() : undefined)} />
                            </div>
                          </div>
                        </td>
                        <td>
                          <OwnerPicker meeting={meeting} ownerId={row.ownerId} name={nameOf(row.ownerId)} badge={badgeOf(row.ownerId)} onPick={pickOwner} />
                        </td>
                        <td>
                          <Dropdown
                            label={t('review.due')}
                            value={row.due}
                            options={dueOptions.map((d) => ({ value: d, label: [dueLabel(d).rel, dueLabel(d).date].filter(Boolean).join(' · ') }))}
                            onChange={(v) => setRow({ ...row, due: v })}
                            trigger={
                              <span className="due">
                                <span className="due__rel">{dueLabel(row.due).rel}</span>
                                {dueLabel(row.due).date && <span className="due__date">{dueLabel(row.due).date}</span>}
                              </span>
                            }
                          />
                        </td>
                        <td>
                          <span className="task-actions">
                            <Button className="task-btn" onClick={cancelRow}>
                              {t('review.cancel')}
                            </Button>
                            <Button variant="ink" className="task-btn" onClick={saveRow} disabled={!row.title.trim()}>
                              {t('review.saveShort')}
                            </Button>
                          </span>
                        </td>
                      </tr>
                    ) : (
                      <tr key={task.id} className={task.confirmed ? 'is-confirmed' : undefined}>
                        <td>
                          {/* Confirm this item: a checkbox leads the row; the whole text is its label, so tapping the task toggles it. */}
                          <label className="task-check">
                            <input
                              type="checkbox"
                              className="checkbox"
                              checked={!!task.confirmed}
                              disabled={!!row}
                              aria-label={task.confirmed ? t('review.unconfirmTask', { title: task.title }) : t('review.confirmTask', { title: task.title })}
                              onChange={() => toggleConfirm(task)}
                            />
                            <span className="task-check__text">
                              {task.patient && <span className="summary-table__patient">{task.patient}</span>}
                              <span className="task-table__title">{task.title}</span>
                            </span>
                          </label>
                        </td>
                        <td>
                          <span className="task-owner">
                            <Avatar name={nameOf(task.ownerId)} {...badgeOf(task.ownerId)} />
                            <span className="task-owner__name truncate">{nameOf(task.ownerId)}</span>
                          </span>
                        </td>
                        <td>
                          <span className="due">
                            <span className="due__rel">{dueLabel(task.due).rel}</span>
                            {dueLabel(task.due).date && <span className="due__date">{dueLabel(task.due).date}</span>}
                          </span>
                        </td>
                        <td>
                          {/* Confirming moved to the row checkbox; edit stays here as a quiet pencil. */}
                          <span className="task-actions">
                            <button type="button" className="icon-btn task-edit-btn" aria-label={t('review.editTask', { title: task.title })} onClick={() => setRow(task)} disabled={!!row}>
                              <PencilSimpleIcon size={20} aria-hidden />
                            </button>
                          </span>
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="review__scroll review__transcript">
              <TranscriptLines lines={meeting.transcript} nameOf={nameOf} />
            </div>
          )}
        </section>

        <ParticipantsPanel meeting={meeting} onChange={setParticipants} />

        {/* Confirm-all, the same checkbox as the rows': ticks every item (Send turns on), and unticking takes them all back. */}
        <div className="review__actions">
          {meeting.tasks.length > 0 && (
            <label className="review__confirm-all">
              <input
                type="checkbox"
                className="checkbox"
                ref={(el) => {
                  if (el) el.indeterminate = someConfirmed; // "partial": a dash, not a tick
                }}
                checked={allConfirmed}
                disabled={!!row}
                onChange={() => setAllConfirmed(!allConfirmed)}
              />
              <span className="review__confirm-text">
                {allConfirmed ? t('review.allConfirmed') : t('review.allCorrect')}
                {someConfirmed && <span className="note">{confirmed}/{meeting.tasks.length}</span>}
              </span>
            </label>
          )}
          <div className="review__actions-row">
            <Button className="review__btn" onClick={() => setPreviewOpen(true)}>
              {t('review.preview')}
            </Button>
            <Button variant="primary" className="review__btn" onClick={send} disabled={!allConfirmed} title={sendBlocked}>
              {t('review.send')}
            </Button>
          </div>
        </div>
      </div>
      {/* The MoM exactly as it will be sent, in a popup; download from here, or close and keep editing. */}
      {previewOpen && (
        <Dialog title={t('review.preview')} onClose={() => setPreviewOpen(false)} className="modal--mom">
          <MomPreview meeting={meeting} />
          <div className="page__actions" style={{ paddingTop: 0 }}>
            <Button icon={<DownloadSimpleIcon size={20} aria-hidden />} onClick={() => void downloadMomPdf(meeting, t, lang)}>
              {t('record.download')}
            </Button>
            <Button
              variant="primary"
              icon={<PaperPlaneTiltIcon size={20} aria-hidden />}
              disabled={!allConfirmed}
              title={sendBlocked}
              onClick={() => {
                setPreviewOpen(false);
                send();
              }}
            >
              {t('review.send')}
            </Button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
