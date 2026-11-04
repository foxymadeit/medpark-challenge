import { useI18n } from '../i18n/I18nProvider';
import { formatDayMonth, formatFullDate } from '../lib/format';
import { meetingHeading, speakerNamer, summaryProse } from '../lib/meeting';
import { useStore } from '../store/AppStore';
import type { Meeting } from '../types';
import { groupTasks } from './Minutes';
import { momFileName } from '../lib/momPdf';
import { FilePdfIcon } from '@phosphor-icons/react';

/**
 * The final MoM as it goes out, as text: the summary as running text, then action items grouped by owner,
 * one row each: Patient/topic · Task · Date.
 * Same content as the PDF.
 */
export function MomPreview({ meeting }: { meeting: Meeting }) {
  const { t, lang } = useI18n();
  const { resolvePerson } = useStore();
  const nameOf = speakerNamer(meeting, resolvePerson, t);
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
          <dd>{t('email.subjectLine', { heading: meetingHeading(meeting, lang) })}</dd>
        </div>
      </dl>
      <article className="mom-preview">
        <h3 className="mom-preview__title">
          {meetingHeading(meeting, lang, formatFullDate)}
        </h3>
        <p className="note">{t('mom.meta', { type: t(`types.${meeting.type}`), n: meeting.durationMin })}</p>

        <h4 className="mom-preview__h">{t('review.summary')}</h4>
        {meeting.summary?.length ? (
          <p className="mom-preview__summary">{summaryProse(meeting.summary)}</p>
        ) : (
          <p className="note">{t('review.noSummary')}</p>
        )}

        <h4 className="mom-preview__h">{t('mom.actions')}</h4>
        {groups.length === 0 && <p className="note">{t('pdf.noTasks')}</p>}
        {groups.map((g) => (
          <section key={g.ownerId} className="mom-preview__owner">
            <p className="mom-preview__owner-name">{nameOf(g.ownerId)}</p>
            <ul className="mom-preview__tasks">
              {g.patients.flatMap((p) =>
                p.tasks.map((task) => (
                  <li key={task.id}>
                    <span className="mom-preview__patient">{p.patient}</span>
                    <span className="mom-preview__task">{task.title}</span>
                    <span className="mom-preview__due">{formatDayMonth(task.due, lang)}</span>
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
