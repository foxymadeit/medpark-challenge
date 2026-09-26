import { useI18n } from '../i18n/I18nProvider';
import { dueRelative, formatDayMonth, formatFullDate } from '../lib/format';
import { speakerNamer } from '../lib/meeting';
import { useStore } from '../store/AppStore';
import type { Meeting } from '../types';
import { groupTasks } from './Minutes';
import { momFileName } from '../lib/momPdf';
import { FilePdfIcon } from '@phosphor-icons/react';

/**
 * The MoM as it goes out, as text: title, participants, summary, then tasks grouped by owner with deadlines.
 * Same content as the PDF: participants, summary, tasks (no transcript).
 */
export function MomPreview({ meeting }: { meeting: Meeting }) {
  const { t, lang } = useI18n();
  const { resolvePerson } = useStore();
  const nameOf = speakerNamer(meeting, resolvePerson, t);
  const due = (iso: string) => {
    const r = dueRelative(meeting.date, iso);
    return r ? `${t(r.key, r.vars)} · ${formatDayMonth(iso, lang)}` : formatDayMonth(iso, lang);
  };
  const groups = groupTasks(meeting.tasks);

  const recipients = meeting.participants.map((p) => p.email ?? resolvePerson(p.personId)?.email).filter(Boolean) as string[];

  // Shown as the email that goes out: headers, the MoM as text, and the same MoM attached as PDF.
  return (
    <div className="mom-email">
      <dl className="mom-email__head">
        <div>
          <dt>{t('email.to')}</dt>
          <dd>{recipients.join(', ') || '—'}</dd>
        </div>
        <div>
          <dt>{t('email.subject')}</dt>
          <dd>{t('email.subjectLine', { title: meeting.title, date: formatDayMonth(meeting.date, lang) })}</dd>
        </div>
      </dl>
      <article className="mom-preview">
        <p className="mom-preview__plate">{t('pdf.title')}</p>
        <h3 className="mom-preview__title">{meeting.title}</h3>
        <p className="note">{t('record.metaUnsent', { type: t(`types.${meeting.type}`), date: formatFullDate(meeting.date, lang), n: meeting.durationMin })}</p>

        <h4 className="mom-preview__h">{t('record.participants')}</h4>
        <table className="mom-preview__people">
          <thead>
            <tr>
              <th scope="col">{t('pdf.colName')}</th>
              <th scope="col">{t('pdf.colRole')}</th>
              <th scope="col">{t('pdf.colEmail')}</th>
            </tr>
          </thead>
          <tbody>
            {meeting.participants.map((p) => (
              <tr key={p.personId}>
                <td className="mom-preview__person">{p.name}</td>
                <td>{p.roleThen || '—'}</td>
                <td className="mom-preview__email">{p.email ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h4 className="mom-preview__h">{t('review.summary')}</h4>
        {meeting.summary?.length ? (
          <ul className="mom-preview__list">
            {meeting.summary.map((point, i) => (
              <li key={i}>{point}</li>
            ))}
          </ul>
        ) : (
          <p className="note">{t('review.noSummary')}</p>
        )}

        <h4 className="mom-preview__h">{t('review.tasks')}</h4>
        {groups.length === 0 && <p className="note">{t('pdf.noTasks')}</p>}
        {groups.map((g) => (
          <section key={g.ownerId} className="mom-preview__owner">
            <p className="mom-preview__owner-name">{nameOf(g.ownerId)}</p>
            <ul className="mom-preview__tasks">
              {g.patients.flatMap((p) =>
                p.tasks.map((task) => (
                  <li key={task.id}>
                    <span>
                      {task.title}
                      {p.patient && <span className="mom-preview__patient"> · {p.patient}</span>}
                    </span>
                    <span className="mom-preview__due">{due(task.due)}</span>
                  </li>
                )),
              )}
            </ul>
          </section>
        ))}
      </article>
      <p className="mom-email__attachment">
        <FilePdfIcon size={20} aria-hidden />
        <span className="truncate">{momFileName(meeting)}</span>
        <span className="note">{t('email.attached')}</span>
      </p>
    </div>
  );
}
