import { CheckIcon, PaperPlaneTiltIcon, PencilSimpleIcon, StopIcon, WarningIcon } from '@phosphor-icons/react';
import { useEffect, useRef, useState } from 'react';
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Button } from '../components/Button';
import { Dropdown } from '../components/Dropdown';
import { groupTasks, TranscriptLines } from '../components/Minutes';
import { Segmented } from '../components/Segmented';
import { useI18n } from '../i18n/I18nProvider';
import { addDays, daysBetween, formatCountdown, formatDayMonth, formatWeekdayDate, isEmail } from '../lib/format';
import { useStore } from '../store/AppStore';
import type { Meeting, Task } from '../types';

type Mode = 'manual' | 'auto';

function useDueLabel(meetingDate: string) {
  const { t, lang } = useI18n();
  return (iso: string, withDate = false) => {
    const d = daysBetween(meetingDate, iso);
    const rel = d === 0 ? t('review.today') : d === 1 ? t('review.tomorrow') : null;
    if (rel) return withDate ? `${rel}, ${formatDayMonth(iso, lang)}` : rel;
    return formatWeekdayDate(iso, lang);
  };
}

function OwnerEmail({ meeting, personId, name }: { meeting: Meeting; personId: string; name: string }) {
  const { t } = useI18n();
  const { updatePerson, updateMeeting, resolvePerson } = useStore();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState('');
  const email = resolvePerson(personId)?.email ?? meeting.participants.find((p) => p.personId === personId)?.email;

  if (email) return <span className="t-body-sm c-secondary">{email}</span>;
  if (editing)
    return (
      <input
        autoFocus
        type="email"
        className="input input--inline owner-email"
        aria-label={t('review.emailFor', { name })}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={() => {
          if (isEmail(value)) {
            updatePerson(personId, { email: value.trim() });
            updateMeeting(meeting.id, { participants: meeting.participants.map((p) => (p.personId === personId ? { ...p, email: value.trim() } : p)) });
          }
          setEditing(false);
        }}
        onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
      />
    );
  return (
    <span className="row t-body-sm c-secondary" style={{ gap: 4 }}>
      <WarningIcon size={16} aria-hidden color="var(--sm-ink-primary)" />
      {t('review.noEmail')} ·{' '}
      <button type="button" className="inline-link" onClick={() => setEditing(true)} aria-label={t('review.emailFor', { name })}>
        {t('review.addEmail')}
      </button>
    </span>
  );
}

/** 05 / 05b / 05c — Review the AI minutes, then send. */
export function Review() {
  const { t, lang } = useI18n();
  const { id } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { meetings, setTasks, sendMeeting, resolvePerson, correctToken, preferences } = useStore();
  const autoSendSeconds = preferences.autoSendSeconds;
  const meeting = meetings.find((m) => m.id === id);
  // Default mode comes from Settings; the URL (?mode=) overrides it.
  const mode: Mode = (params.get('mode') as Mode | null) ?? preferences.reviewMode;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Task[]>([]);
  const [openTask, setOpenTask] = useState<string | null>(null);
  const [remaining, setRemaining] = useState(autoSendSeconds);
  const dueLabel = useDueLabel(meeting?.date ?? '');

  const setMode = (m: Mode) => {
    setEditing(false);
    setRemaining(autoSendSeconds);
    setParams({ mode: m }, { replace: true });
  };

  const sent = useRef(false);
  const send = () => {
    if (!meeting || sent.current) return;
    sent.current = true;
    sendMeeting(meeting.id);
    navigate(`/sent/${meeting.id}`);
  };

  // Auto mode countdown.
  useEffect(() => {
    if (mode !== 'auto') return;
    const started = performance.now();
    const timer = setInterval(() => setRemaining(Math.max(0, autoSendSeconds - (performance.now() - started) / 1000)), 100);
    return () => clearInterval(timer);
  }, [mode]);
  useEffect(() => {
    if (mode === 'auto' && remaining <= 0) send();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, remaining]);

  if (!meeting) return <Navigate to="/history" replace />;
  // After our own send(), navigation to /sent is in flight (router uses transitions) — don't redirect.
  if (meeting.status === 'sent' && !sent.current) return <Navigate to={`/history/${meeting.id}`} replace />;
  if (meeting.status === 'processing') return <Navigate to={`/processing/${meeting.id}`} replace />;

  const nameOf = (pid: string) => meeting.participants.find((p) => p.personId === pid)?.name ?? resolvePerson(pid)?.name ?? pid;
  const tasks = editing ? draft : meeting.tasks;
  const groups = groupTasks(tasks);
  const recipients = meeting.participants.filter((p) => p.email || resolvePerson(p.personId)?.email).length;
  const dueOptions = Array.from({ length: 8 }, (_, i) => addDays(meeting.date, i));

  const startEdit = () => {
    setDraft(meeting.tasks);
    setOpenTask(meeting.tasks[0]?.id ?? null);
    setEditing(true);
  };
  const patchTask = (taskId: string, patch: Partial<Task>) => setDraft((d) => d.map((x) => (x.id === taskId ? { ...x, ...patch } : x)));

  return (
    <div className="page review">
      <header className="review__header">
        <div className="stack" style={{ gap: 4 }}>
          <h1 className="t-h1">
            {meeting.title} · {formatDayMonth(meeting.date, lang)}
          </h1>
          <p className="note">{t('review.meta', { type: t(`types.${meeting.type}`), n: meeting.durationMin, count: meeting.participants.length })}</p>
        </div>
        <Segmented<Mode>
          label={t('review.mode')}
          value={mode}
          onChange={setMode}
          options={[
            { value: 'manual', label: t('review.manual') },
            { value: 'auto', label: t('review.auto') },
          ]}
        />
      </header>

      <div className="review__panes">
        <section className="card review__pane review__pane--transcript" aria-labelledby="rv-transcript" tabIndex={0}>
          <div className="stack" style={{ gap: 4 }}>
            <h2 id="rv-transcript" className="t-h3">
              {t('review.transcript')}
            </h2>
            <p className="note">{t('review.highlighted')}</p>
            <p className="note">{t('review.word.hint')}</p>
          </div>
          <TranscriptLines lines={meeting.transcript} nameOf={nameOf} onCorrect={(line, token, value) => correctToken(meeting.id, line, token, value)} />
        </section>

        <section className="card review__pane review__pane--tasks" aria-labelledby="rv-tasks" tabIndex={0}>
          <h2 id="rv-tasks" className="t-h3">
            {t('review.tasks')}
          </h2>
          {groups.map((g) => (
            <div key={g.ownerId} className="tile owner-group">
              <div className="row owner-group__head">
                <span className="t-strong">{nameOf(g.ownerId)}</span>
                <OwnerEmail meeting={meeting} personId={g.ownerId} name={nameOf(g.ownerId)} />
              </div>
              {g.patients.map((p) => (
                <div key={p.patient} className="stack" style={{ gap: 12 }}>
                  <p className="t-plate c-secondary">{t('review.patient', { name: p.patient })}</p>
                  {p.tasks.map((task) =>
                    editing && openTask === task.id ? (
                      <div key={task.id} className="task-editor">
                        <div className="field">
                          <label className="field__label" htmlFor={`task-${task.id}`}>
                            {t('review.task')}
                          </label>
                          <input id={`task-${task.id}`} className="input input--active" value={task.title} onChange={(e) => patchTask(task.id, { title: e.target.value })} autoFocus />
                        </div>
                        <div className="row" style={{ gap: 12, alignItems: 'flex-start' }}>
                          <div className="field">
                            <span className="field__label" id={`own-${task.id}`}>
                              {t('review.owner')}
                            </span>
                            <Dropdown variant="field" labelledBy={`own-${task.id}`} label={t('review.owner')} value={task.ownerId} options={meeting.participants.map((x) => ({ value: x.personId, label: x.name }))} onChange={(v) => patchTask(task.id, { ownerId: v })} />
                          </div>
                          <div className="field">
                            <span className="field__label" id={`due-${task.id}`}>
                              {t('review.due')}
                            </span>
                            <Dropdown variant="field" labelledBy={`due-${task.id}`} label={t('review.due')} value={task.due} options={dueOptions.map((d) => ({ value: d, label: dueLabel(d, true) }))} onChange={(v) => patchTask(task.id, { due: v })} />
                          </div>
                        </div>
                      </div>
                    ) : editing ? (
                      <button key={task.id} type="button" className="task task--button" aria-label={t('review.editTask', { title: task.title })} onClick={() => setOpenTask(task.id)}>
                        <span className="t-body-md">{task.title}</span>
                        <span className="t-data-sm">{dueLabel(task.due)}</span>
                      </button>
                    ) : (
                      <div key={task.id} className="task">
                        <span className="t-body-md">{task.title}</span>
                        <span className="t-data-sm">{dueLabel(task.due)}</span>
                      </div>
                    ),
                  )}
                </div>
              ))}
            </div>
          ))}
        </section>
      </div>

      <div className="action-bar">
        {mode === 'auto' ? (
          <>
            <div className="action-bar__line" style={{ width: `${(remaining / autoSendSeconds) * 100}%` }} aria-hidden />
            <p className="action-bar__left row" role="timer" aria-live="off">
              <span className="note">{t('review.sendingIn', { count: recipients })}</span>
              <span className="t-data-md">{formatCountdown(remaining)}</span>
            </p>
            <Button icon={<StopIcon size={20} aria-hidden />} onClick={() => setMode('manual')}>
              {t('review.stopReview')}
            </Button>
            <Button variant="primary" icon={<PaperPlaneTiltIcon size={20} aria-hidden />} onClick={send}>
              {t('review.sendNow')}
            </Button>
          </>
        ) : (
          <>
            <p className="action-bar__left note">{t('review.teach')}</p>
            {editing ? (
              <>
                <Button onClick={() => setEditing(false)}>{t('review.cancel')}</Button>
                <Button
                  variant="primary"
                  icon={<CheckIcon size={20} aria-hidden />}
                  onClick={() => {
                    setTasks(meeting.id, draft);
                    setEditing(false);
                  }}
                >
                  {t('review.save')}
                </Button>
              </>
            ) : (
              <>
                <Button icon={<PencilSimpleIcon size={20} aria-hidden />} onClick={startEdit}>
                  {t('review.edit')}
                </Button>
                <Button variant="primary" icon={<PaperPlaneTiltIcon size={20} aria-hidden />} onClick={send}>
                  {t('review.send')}
                </Button>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
