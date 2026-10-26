import { CheckIcon, DownloadSimpleIcon, FileMagnifyingGlassIcon, PaperPlaneTiltIcon, PencilSimpleIcon, PlusIcon } from '@phosphor-icons/react';
import { useRef, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { Button } from '../components/Button';
import { SummaryPoints } from '../components/SummaryPoints';
import { Dialog } from '../components/Dialog';
import { MomPreview } from '../components/MomPreview';
import { Dropdown } from '../components/Dropdown';
import { TranscriptLines } from '../components/Minutes';
import { OwnerPicker } from '../components/OwnerPicker';
import { PeopleStack } from '../components/PeopleStack';
import { RecipientsField } from '../components/RecipientsField';
import { Segmented } from '../components/Segmented';
import { useI18n } from '../i18n/I18nProvider';
import { addDays, DUE_OFFSETS, dueRelative, formatDayMonth, formatWeekdayDate, uid } from '../lib/format';
import { speakerNamer } from '../lib/meeting';
import { downloadMomPdf } from '../lib/momPdf';
import { useStore } from '../store/AppStore';
import type { Meeting, ParticipantSnapshot, Task } from '../types';

/** Deadline as said in the meeting ("Tomorrow", "In 3 days"…) plus the date it resolves to. */
function useDueLabel(meetingDate: string) {
  const { t, lang } = useI18n();
  return (iso: string) => {
    const rel = dueRelative(meetingDate, iso);
    const date = formatWeekdayDate(iso, lang);
    return { rel: rel ? t(rel.key, rel.vars) : date, date: rel ? date : '' };
  };
}

/** Meeting title with a pen; Enter saves, Esc cancels. */
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
    <div className="row" style={{ gap: 8 }}>
      <h1 className="t-h1">
        {meeting.title} · {formatDayMonth(meeting.date, lang)}
      </h1>
      <button type="button" className="icon-btn edit-btn" aria-label={t('review.renameLabel')} title={t('review.renameLabel')} onClick={() => setEditing(true)}>
        <PencilSimpleIcon size={16} aria-hidden />
      </button>
    </div>
  );
}

/** 05 — Review the AI minutes, then send. MoM tab: Summary and Tasks (each scrolls on its own), confirm every action item;
 * Transcript tab: read-only. Recipients and the buttons sit under the containers, always visible. */
export function Review() {
  const { t, lang } = useI18n();
  const { id } = useParams();
  const navigate = useNavigate();
  const { account, meetings, setTasks, setSummary, sendMeeting, resolvePerson, updateMeeting } = useStore();
  const meeting = meetings.find((m) => m.id === id);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [row, setRow] = useState<Task | null>(null);
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

  const nameOf = speakerNamer(meeting, resolvePerson, t);
  const tasks = [...meeting.tasks].sort((a, b) => a.due.localeCompare(b.due));
  const dueOptions = [...new Set([...DUE_OFFSETS.map((n) => addDays(meeting.date, n)), ...(row ? [row.due] : [])])].sort();
  // Send is on only when every action item is confirmed.
  const confirmed = meeting.tasks.filter((x) => x.confirmed).length;
  const allConfirmed = confirmed === meeting.tasks.length;
  const toggleConfirm = (task: Task) => setTasks(meeting.id, meeting.tasks.map((x) => (x.id === task.id ? { ...x, confirmed: !x.confirmed } : x)));

  const isNew = !!row && !meeting.tasks.some((x) => x.id === row.id);
  // A new task shows as an editing row on top; it's only added once saved.
  const rows = isNew && row ? [row, ...tasks] : tasks;
  const addTask = () => {
    const task: Task = { id: uid('task'), ownerId: account?.personId && meeting.participants.some((p) => p.personId === account.personId) ? account.personId : meeting.participants[0]?.personId ?? '', patient: '', title: '', due: addDays(meeting.date, 1) };
    setEditingId(task.id);
    setRow(task);
  };
  const startRow = (task: Task) => (setEditingId(task.id), setRow(task));
  const cancelRow = () => (setEditingId(null), setRow(null));
  const saveRow = () => {
    if (row && row.title.trim()) {
      // An edited (or new) action item needs confirming again.
      const clean = { ...row, title: row.title.trim(), patient: row.patient.trim(), confirmed: false };
      setTasks(meeting.id, isNew ? [...meeting.tasks, clean] : meeting.tasks.map((x) => (x.id === row.id ? clean : x)));
    }
    cancelRow();
  };
  // New owner for a task: the whole owner changes (avatar, name, email); someone new joins the meeting too.
  const changeOwner = (task: Task, owner: ParticipantSnapshot) => {
    const participants = meeting.participants.some((p) => p.personId === owner.personId) ? meeting.participants : [...meeting.participants, owner];
    if (row && row.id === task.id) setRow({ ...row, ownerId: owner.personId });
    updateMeeting(meeting.id, {
      participants,
      // Changing the owner counts as an edit: the item needs confirming again.
      tasks: meeting.tasks.map((x) => (x.id === task.id ? { ...x, ownerId: owner.personId, confirmed: false } : x)),
    });
  };
  const ownerCell = (task: Task) => <OwnerPicker meeting={meeting} ownerId={task.ownerId} name={nameOf(task.ownerId)} onPick={(o) => changeOwner(task, o)} />;
  const sendBlocked = allConfirmed ? undefined : t('review.confirmAllFirst');

  return (
    <div className="page review page--fit">
      <header className="review__header">
        <div className="stack" style={{ gap: 4, minWidth: 0 }}>
          <EditableTitle meeting={meeting} />
          <p className="note">{t('review.meta', { type: t(`types.${meeting.type}`), n: meeting.durationMin, count: meeting.participants.length })}</p>
        </div>
        <PeopleStack ids={meeting.participants.map((p) => p.personId)} names={false} max={6} />
      </header>

      <div className="review__tabs">
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
      </div>

      {tab === 'mom' ? (
        <div className="review__panes">
          {/* Summary: own scroll; the heading (with Add point) stays put. */}
          <section className="card review__pane review__pane--split" aria-labelledby="rv-summary">
            <SummaryPoints
              points={meeting.summary ?? []}
              onChange={(points) => setSummary(meeting.id, points)}
              head={
                <h2 id="rv-summary" className="review__pane-title">
                  {t('review.summary')}
                </h2>
              }
            />
          </section>

          {/* Tasks: own scroll; the heading (with Add task) and the Owner / Deadline row stay put. */}
          <section className="card review__pane review__pane--split" aria-labelledby="rv-tasks">
            <div className="summary-head summary-head--tasks">
              <h2 id="rv-tasks" className="review__pane-title">
                {t('review.tasks')}
              </h2>
              <button type="button" className="btn btn--ghost summary-head__add" onClick={addTask} disabled={isNew}>
                <PlusIcon size={16} aria-hidden />
                {t('review.addTask')}
              </button>
            </div>
            <div className="review__scroll">
              <table className="summary-table summary-table--tasks">
                <thead>
                  <tr>
                    <th scope="col">
                      {/* "Tasks" is already the heading above; keep the column name for screen readers only. */}
                      <span className="sr-only">{t('review.task')}</span>
                    </th>
                    <th scope="col">{t('review.owner')}</th>
                    <th scope="col">{t('review.due')}</th>
                    <th scope="col">
                      <span className="sr-only">{t('review.actions')}</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((task) =>
                    editingId === task.id && row ? (
                      <tr key={task.id} className="is-editing" onKeyDown={(e) => e.key === 'Escape' && (e.stopPropagation(), cancelRow())}>
                        <td>
                          <input className="input input--inline summary-table__patient-input" aria-label={t('review.patientField')} placeholder={t('review.patientField')} value={row.patient} onChange={(e) => setRow({ ...row, patient: e.target.value })} />
                          <input className="input input--inline" aria-label={t('review.task')} placeholder={t('review.taskPh')} value={row.title} autoFocus onChange={(e) => setRow({ ...row, title: e.target.value })} onKeyDown={(e) => (e.key === 'Enter' ? saveRow() : e.key === 'Escape' ? cancelRow() : undefined)} />
                        </td>
                        <td>{isNew ? <OwnerPicker meeting={meeting} ownerId={row.ownerId} name={nameOf(row.ownerId)} onPick={(o) => (meeting.participants.some((p) => p.personId === o.personId) || updateMeeting(meeting.id, { participants: [...meeting.participants, o] }), setRow({ ...row, ownerId: o.personId }))} /> : ownerCell(task)}</td>
                        <td>
                          <Dropdown variant="field" label={t('review.due')} value={row.due} options={dueOptions.map((d) => ({ value: d, label: [dueLabel(d).rel, dueLabel(d).date].filter(Boolean).join(' · ') }))} onChange={(v) => setRow({ ...row, due: v })} />
                        </td>
                        <td>
                          <span className="task-actions">
                            <Button onClick={cancelRow}>{t('review.cancel')}</Button>
                            <Button variant="ink" onClick={saveRow} disabled={!row.title.trim()}>
                              {t('review.saveShort')}
                            </Button>
                          </span>
                        </td>
                      </tr>
                    ) : (
                      <tr key={task.id} className={task.confirmed ? 'is-confirmed' : undefined}>
                        <td>
                          {task.patient && <span className="summary-table__patient">{t('review.patient', { name: task.patient })}</span>}
                          <span className="t-body-md">{task.title}</span>
                        </td>
                        <td>{ownerCell(task)}</td>
                        <td>
                          <span className="due">
                            <span className="due__rel">{dueLabel(task.due).rel}</span>
                            {dueLabel(task.due).date && <span className="due__date">{dueLabel(task.due).date}</span>}
                          </span>
                        </td>
                        <td>
                          {/* Edit (white) then Confirm (black) at the row's right edge; confirmed → calm "Confirmed ✓", tap again to undo. */}
                          <span className="task-actions">
                            <Button aria-label={t('review.editTask', { title: task.title })} onClick={() => startRow(task)}>
                              {t('review.edit')}
                            </Button>
                            <Button
                              variant={task.confirmed ? 'ghost' : 'ink'}
                              className={`task-confirm${task.confirmed ? ' is-on' : ''}`}
                              aria-pressed={!!task.confirmed}
                              aria-label={task.confirmed ? t('review.unconfirmTask', { title: task.title }) : t('review.confirmTask', { title: task.title })}
                              icon={task.confirmed ? <CheckIcon size={16} weight="bold" aria-hidden /> : undefined}
                              onClick={() => toggleConfirm(task)}
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
          </section>
        </div>
      ) : (
        <div className="review__panes">
          {/* Read-only, one container with its own scroll. */}
          <section className="card review__pane review__pane--fill" aria-labelledby="rv-transcript">
            <h2 id="rv-transcript" className="review__pane-title">
              {t('review.transcript')}
            </h2>
            <div className="review__scroll">
              <TranscriptLines lines={meeting.transcript} nameOf={nameOf} />
            </div>
          </section>
        </div>
      )}

      {/* Under the containers, always visible: who gets the MoM, then Preview / Send (centred on the window). */}
      <div className="review__bottom">
        <div className="review__recipients">
          <span className="review__recipients-label" id="rv-recipients">
            {t('recipients.title')}
          </span>
          <RecipientsField meeting={meeting} onChange={(participants) => updateMeeting(meeting.id, { participants })} />
        </div>
        <div className="review__actions vp-center">
          <p className="action-bar__left note">{t('review.teach')}</p>
          <div className="vp-center__group">
            {meeting.tasks.length > 0 && (
              <span className={`review__confirmed note${allConfirmed ? ' is-done' : ''}`} role="status">
                {t('review.confirmedCount', { n: confirmed, total: meeting.tasks.length })}
              </span>
            )}
            <Button icon={<FileMagnifyingGlassIcon size={20} aria-hidden />} onClick={() => setPreviewOpen(true)}>
              {t('review.preview')}
            </Button>
            <Button variant="ink" icon={<PaperPlaneTiltIcon size={20} aria-hidden />} onClick={send} disabled={!allConfirmed} title={sendBlocked}>
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
              variant="ink"
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
