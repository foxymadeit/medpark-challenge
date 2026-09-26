import { CheckIcon, PaperPlaneTiltIcon, PencilSimpleIcon, WarningIcon, XIcon } from '@phosphor-icons/react';
import { useRef, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { Avatar } from '../components/Avatar';
import { Button } from '../components/Button';
import { Dropdown } from '../components/Dropdown';
import { TranscriptLines } from '../components/Minutes';
import { PeopleStack } from '../components/PeopleStack';
import { useI18n } from '../i18n/I18nProvider';
import { addDays, daysBetween, formatDayMonth, formatWeekdayDate, isEmail } from '../lib/format';
import { lineTokens } from '../lib/transcript';
import { useStore } from '../store/AppStore';
import type { Meeting, Task } from '../types';

function useDueLabel(meetingDate: string) {
  const { t, lang } = useI18n();
  return (iso: string, withDate = false) => {
    const d = daysBetween(meetingDate, iso);
    const rel = d === 0 ? t('review.today') : d === 1 ? t('review.tomorrow') : null;
    if (rel) return withDate ? `${rel}, ${formatDayMonth(iso, lang)}` : rel;
    return formatWeekdayDate(iso, lang);
  };
}

/** Small pen button: the one visual cue for "this can be edited". */
function EditButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button type="button" className="icon-btn edit-btn" aria-label={label} title={label} onClick={onClick}>
      <PencilSimpleIcon size={16} aria-hidden />
    </button>
  );
}

/** Owner's email under their name; pen to change it, "add" when missing. */
function OwnerEmail({ meeting, personId, name }: { meeting: Meeting; personId: string; name: string }) {
  const { t } = useI18n();
  const { updatePerson, updateMeeting, resolvePerson } = useStore();
  const email = resolvePerson(personId)?.email ?? meeting.participants.find((p) => p.personId === personId)?.email;
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(email ?? '');
  const [error, setError] = useState(false);

  const commit = () => {
    const v = value.trim();
    if (v && !isEmail(v)) return setError(true);
    if (v && v !== email) {
      updatePerson(personId, { email: v });
      updateMeeting(meeting.id, { participants: meeting.participants.map((p) => (p.personId === personId ? { ...p, email: v } : p)) });
    }
    setError(false);
    setEditing(false);
  };

  if (editing)
    return (
      <span className="stack" style={{ gap: 2 }}>
        <input
          autoFocus
          type="email"
          className="input input--inline owner-email"
          placeholder={t('addParticipant.emailPh')}
          aria-label={t('review.emailFor', { name })}
          aria-invalid={error || undefined}
          value={value}
          onChange={(e) => (setValue(e.target.value), setError(false))}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commit();
            if (e.key === 'Escape') (setValue(email ?? ''), setError(false), setEditing(false));
          }}
        />
        {error && <span className="field__error">{t('common.emailInvalid')}</span>}
      </span>
    );
  return (
    <span className="owner-email-line">
      {email ? (
        <span className="t-body-sm c-secondary truncate">{email}</span>
      ) : (
        <span className="row t-body-sm c-secondary" style={{ gap: 4 }}>
          <WarningIcon size={14} aria-hidden color="var(--sm-signal-danger)" />
          {t('review.noEmail')}
        </span>
      )}
      <EditButton label={t('review.emailFor', { name })} onClick={() => setEditing(true)} />
    </span>
  );
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
      <EditButton label={t('review.renameLabel')} onClick={() => setEditing(true)} />
    </div>
  );
}

/** 05 — Review the AI minutes, then send. Every editable value carries a pen. */
export function Review() {
  const { t } = useI18n();
  const { id } = useParams();
  const navigate = useNavigate();
  const { meetings, setTasks, sendMeeting, resolvePerson, correctToken, removeToken, updateMeeting } = useStore();
  // Last removal, so a slip can be undone.
  const [removed, setRemoved] = useState<{ word: string; transcript: Meeting['transcript'] } | null>(null);
  const meeting = meetings.find((m) => m.id === id);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [row, setRow] = useState<Task | null>(null);
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

  const nameOf = (pid: string) => meeting.participants.find((p) => p.personId === pid)?.name ?? resolvePerson(pid)?.name ?? pid;
  const tasks = [...meeting.tasks].sort((a, b) => a.due.localeCompare(b.due));
  const dueOptions = Array.from({ length: 8 }, (_, i) => addDays(meeting.date, i));

  const startRow = (task: Task) => (setEditingId(task.id), setRow(task));
  const cancelRow = () => (setEditingId(null), setRow(null));
  const saveRow = () => {
    if (row && row.title.trim()) setTasks(meeting.id, meeting.tasks.map((x) => (x.id === row.id ? { ...row, title: row.title.trim() } : x)));
    cancelRow();
  };

  return (
    <div className="page review">
      <header className="review__header">
        <div className="stack" style={{ gap: 4, minWidth: 0 }}>
          <EditableTitle meeting={meeting} />
          <p className="note">{t('review.meta', { type: t(`types.${meeting.type}`), n: meeting.durationMin, count: meeting.participants.length })}</p>
        </div>
        <PeopleStack ids={meeting.participants.map((p) => p.personId)} names={false} max={6} />
      </header>

      <div className="review__panes">
        <section className="card review__pane review__pane--transcript" aria-labelledby="rv-transcript" tabIndex={0}>
          <div className="stack" style={{ gap: 4 }}>
            <h2 id="rv-transcript" className="section-title">
              {t('review.transcript')}
            </h2>
            <p className="note hint">
              <PencilSimpleIcon size={14} aria-hidden />
              <span>{t('review.word.hint')}</span>
            </p>
          </div>
          {removed && (
            <p className="undo-bar" role="status">
              <span className="truncate">{t('review.word.removed', { word: removed.word })}</span>
              <button type="button" className="link-btn" onClick={() => (updateMeeting(meeting.id, { transcript: removed.transcript }), setRemoved(null))}>
                {t('review.word.undo')}
              </button>
            </p>
          )}
          <TranscriptLines
            lines={meeting.transcript}
            nameOf={nameOf}
            onCorrect={(line, token, value) => (correctToken(meeting.id, line, token, value), setRemoved(null))}
            onRemove={(line, token) => {
              const tok = lineTokens(meeting.transcript[line])[token];
              setRemoved({ word: tok?.text ?? '', transcript: meeting.transcript });
              removeToken(meeting.id, line, token);
            }}
          />
        </section>

        <section className="card review__pane review__pane--tasks" aria-labelledby="rv-tasks" tabIndex={0}>
          <h2 id="rv-tasks" className="section-title">
            {t('review.tasks')}
          </h2>
          <table className="summary-table">
            <thead>
              <tr>
                <th scope="col">{t('review.task')}</th>
                <th scope="col">{t('review.owner')}</th>
                <th scope="col">{t('review.due')}</th>
                <th scope="col">
                  <span className="sr-only">{t('review.edit')}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) =>
                editingId === task.id && row ? (
                  <tr key={task.id} className="is-editing">
                    <td>
                      <span className="summary-table__patient">{t('review.patient', { name: task.patient })}</span>
                      <input className="input input--inline" aria-label={t('review.task')} value={row.title} autoFocus onChange={(e) => setRow({ ...row, title: e.target.value })} onKeyDown={(e) => (e.key === 'Enter' ? saveRow() : e.key === 'Escape' ? cancelRow() : undefined)} />
                    </td>
                    <td>
                      <Dropdown variant="field" label={t('review.owner')} value={row.ownerId} options={meeting.participants.map((x) => ({ value: x.personId, label: x.name }))} onChange={(v) => setRow({ ...row, ownerId: v })} />
                    </td>
                    <td>
                      <Dropdown variant="field" label={t('review.due')} value={row.due} options={dueOptions.map((d) => ({ value: d, label: dueLabel(d, true) }))} onChange={(v) => setRow({ ...row, due: v })} />
                    </td>
                    <td>
                      <span className="row" style={{ gap: 4 }}>
                        <button type="button" className="icon-btn icon-btn--confirm" aria-label={t('review.save')} title={t('review.save')} onClick={saveRow} disabled={!row.title.trim() || (row.title === task.title && row.ownerId === task.ownerId && row.due === task.due)}>
                          <CheckIcon size={16} aria-hidden />
                        </button>
                        <button type="button" className="icon-btn" aria-label={t('review.cancel')} title={t('review.cancel')} onClick={cancelRow}>
                          <XIcon size={16} aria-hidden />
                        </button>
                      </span>
                    </td>
                  </tr>
                ) : (
                  <tr key={task.id}>
                    <td>
                      <span className="summary-table__patient">{t('review.patient', { name: task.patient })}</span>
                      <span className="t-body-md">{task.title}</span>
                    </td>
                    <td>
                      <span className="summary-table__owner">
                        <Avatar name={nameOf(task.ownerId)} />
                        <span className="who__text">
                          <span className="who__name truncate">{nameOf(task.ownerId)}</span>
                          <OwnerEmail meeting={meeting} personId={task.ownerId} name={nameOf(task.ownerId)} />
                        </span>
                      </span>
                    </td>
                    <td className="t-data-sm">{dueLabel(task.due)}</td>
                    <td>
                      <EditButton label={t('review.editTask', { title: task.title })} onClick={() => startRow(task)} />
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </section>
      </div>

      <div className="action-bar">
        <p className="action-bar__left note">{t('review.teach')}</p>
        <Button variant="primary" icon={<PaperPlaneTiltIcon size={20} aria-hidden />} onClick={send}>
          {t('review.send')}
        </Button>
      </div>
    </div>
  );
}
