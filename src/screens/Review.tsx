import { DownloadSimpleIcon, PaperPlaneTiltIcon, PlusIcon } from '@phosphor-icons/react';
import { useLayoutEffect, useRef, useState, type TextareaHTMLAttributes } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { Avatar } from '../components/Avatar';
import { Button } from '../components/Button';
import { SummaryPoints } from '../components/SummaryPoints';
import { Dialog } from '../components/Dialog';
import { MomPreview } from '../components/MomPreview';
import { Dropdown } from '../components/Dropdown';
import { TranscriptLines } from '../components/Minutes';
import { OwnerPicker } from '../components/OwnerPicker';
import { ParticipantsPanel } from '../components/ParticipantsPanel';
import { Segmented } from '../components/Segmented';
import { useI18n } from '../i18n/I18nProvider';
import { addDays, DUE_OFFSETS, dueRelative, formatWeekdayDate, uid } from '../lib/format';
import { meetingHeading, speakers } from '../lib/meeting';
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

/** Meeting title: click it to rename; Enter saves, Esc cancels. */
function EditableTitle({ meeting }: { meeting: Meeting }) {
  const { t, lang } = useI18n();
  const { updateMeeting } = useStore();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(meeting.title);
  const commit = () => {
    if (value.trim()) updateMeeting(meeting.id, { title: value.trim() });
    else setValue(meeting.title);
    setEditing(false);
  };
  if (editing)
    return (
      <input
        autoFocus
        className="input review__title-input"
        aria-label={t('review.titleLabel')}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit();
          if (e.key === 'Escape') (setValue(meeting.title), setEditing(false));
        }}
      />
    );
  return (
    <h1 className="t-h1 review__title">
      <button type="button" className="review__title-btn" title={t('review.renameLabel')} onClick={() => setEditing(true)}>
        {meetingHeading(meeting, lang)}
      </button>
    </h1>
  );
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
  // Send is on only when every action item is confirmed.
  const confirmed = meeting.tasks.filter((x) => x.confirmed).length;
  const allConfirmed = confirmed === meeting.tasks.length;
  const toggleConfirm = (task: Task) => setTasks(meeting.id, meeting.tasks.map((x) => (x.id === task.id ? { ...x, confirmed: !x.confirmed } : x)));
  const setParticipants = (participants: ParticipantSnapshot[]) => updateMeeting(meeting.id, { participants });

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
        <header className="review__header">
          <div className="stack" style={{ gap: 'var(--sm-space-1)', minWidth: 0 }}>
            <EditableTitle meeting={meeting} />
            <p className="note">{t('review.meta', { type: t(`types.${meeting.type}`), n: meeting.durationMin, count: meeting.participants.length })}</p>
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
                <SummaryPoints
                  points={meeting.summary ?? []}
                  onChange={(points) => setSummary(meeting.id, points)}
                  head={
                    <span className="review__count-head">
                      <h2 id="rv-summary" className="review__pane-title">
                        {t('review.summary')}
                      </h2>
                      <span className="note">{t('review.pointsCount', { count: meeting.summary?.length ?? 0 })}</span>
                    </span>
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
                  {rows.map((task, i) =>
                    row && row.id === task.id ? (
                      <tr key={task.id} className="is-editing" onKeyDown={(e) => e.key === 'Escape' && (e.stopPropagation(), cancelRow())}>
                        {/* Edit: same columns as reading; the row lights up across the card (a backdrop cell, last, spanning the
                            whole grid line under the cells), the texts become fields. Every cell is placed on the row's grid line
                            (header = 1) and its own column, so they sit over the backdrop instead of being moved aside. */}
                        <td style={{ gridRow: i + 2, gridColumn: 1 }}>
                          <input className="task-edit summary-table__patient" aria-label={t('review.patientField')} placeholder={t('review.patientField')} value={row.patient} onChange={(e) => setRow({ ...row, patient: e.target.value })} />
                          <InlineText className="task-edit task-table__title" aria-label={t('review.task')} placeholder={t('review.taskPh')} value={row.title} autoFocus onChange={(e) => setRow({ ...row, title: e.target.value })} onKeyDown={(e) => (e.key === 'Enter' ? (e.preventDefault(), saveRow()) : e.key === 'Escape' ? cancelRow() : undefined)} />
                        </td>
                        <td style={{ gridRow: i + 2, gridColumn: 2 }}>
                          <OwnerPicker meeting={meeting} ownerId={row.ownerId} name={nameOf(row.ownerId)} badge={badgeOf(row.ownerId)} onPick={pickOwner} />
                        </td>
                        <td style={{ gridRow: i + 2, gridColumn: 3 }}>
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
                        <td style={{ gridRow: i + 2, gridColumn: 4 }}>
                          <span className="task-actions">
                            <Button className="task-btn" onClick={cancelRow}>
                              {t('review.cancel')}
                            </Button>
                            <Button variant="ink" className="task-btn" onClick={saveRow} disabled={!row.title.trim()}>
                              {t('review.saveShort')}
                            </Button>
                          </span>
                        </td>
                        <td className="task-row__backdrop" aria-hidden style={{ gridRow: i + 2 }} />
                      </tr>
                    ) : (
                      <tr key={task.id} className={task.confirmed ? 'is-confirmed' : undefined}>
                        <td>
                          {task.patient && <span className="summary-table__patient">{task.patient}</span>}
                          <span className="task-table__title">{task.title}</span>
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
                          {/* Edit then Confirm; confirmed → grey "Confirmed", same size, tap again to undo. */}
                          <span className="task-actions">
                            <Button className="task-btn" aria-label={t('review.editTask', { title: task.title })} onClick={() => setRow(task)} disabled={!!row}>
                              {t('review.edit')}
                            </Button>
                            <Button
                              variant="ink"
                              className={`task-btn task-confirm${task.confirmed ? ' is-on' : ''}`}
                              aria-pressed={!!task.confirmed}
                              aria-label={task.confirmed ? t('review.unconfirmTask', { title: task.title }) : t('review.confirmTask', { title: task.title })}
                              onClick={() => toggleConfirm(task)}
                              disabled={!!row}
                            >
                              {task.confirmed ? t('review.confirmed') : t('review.confirm')}
                            </Button>
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

        {/* Preview / Send centred on the window; "confirmed 2/12" just right of Send. */}
        <div className="review__actions">
          <Button className="review__btn" onClick={() => setPreviewOpen(true)}>
            {t('review.preview')}
          </Button>
          <Button variant="primary" className="review__btn" onClick={send} disabled={!allConfirmed} title={sendBlocked}>
            {t('review.send')}
          </Button>
          {meeting.tasks.length > 0 && (
            <span className={`review__confirmed note${allConfirmed ? ' is-done' : ''}`} role="status">
              {t('review.confirmedCount', { n: confirmed, total: meeting.tasks.length })}
            </span>
          )}
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
