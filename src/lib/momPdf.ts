import type { Content, TDocumentDefinitions } from 'pdfmake/interfaces';
import { groupTasks } from '../components/Minutes';
import { meetingHeading, speakerNamer, summaryProse } from './meeting';
import type { Lang } from '../i18n/I18nProvider';
import type { Meeting } from '../types';
import { formatDayMonth, formatFullDate, todayISO } from './format';

type T = (key: string, vars?: Record<string, string | number>) => string;

// pdfmake can't read CSS variables: these mirror --sm-ink-primary / --sm-ink-secondary / --sm-surface-hairline in styles/tokens.css.
const INK = '#101010';
const INK_2 = '#5B544B';
const HAIRLINE = '#EAE6DF';

const hairlineTable = {
  hLineWidth: (i: number) => (i === 0 ? 0 : 0.75),
  vLineWidth: () => 0,
  hLineColor: () => HAIRLINE,
  paddingLeft: (i: number) => (i === 0 ? 0 : 8),
  paddingRight: () => 8,
  paddingTop: () => 6,
  paddingBottom: () => 6,
};

function safeName(s: string) {
  return s.replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '') || 'minutes';
}

/**
 * Builds the Minutes of Meeting as a real PDF file.
 * pdfmake is lazy-loaded (≈1 MB) so it only costs anything when someone clicks Download or Preview.
 * Its bundled Roboto covers Romanian diacritics and Cyrillic.
 */
async function buildMomPdf(meeting: Meeting, t: T, lang: Lang) {
  const [{ default: pdfMake }, { default: vfs }] = await Promise.all([import('pdfmake/build/pdfmake'), import('pdfmake/build/vfs_fonts')]);
  pdfMake.vfs = vfs;

  const date = formatFullDate(meeting.date, lang);
  const nameOf = speakerNamer(meeting, () => undefined, t);
  const type = t(`types.${meeting.type}`);

  const tasks: Content[] = groupTasks(meeting.tasks).flatMap((g) => [
    { text: nameOf(g.ownerId), style: 'owner' },
    {
      table: {
        headerRows: 1,
        widths: [110, '*', 70],
        body: [
          [{ text: t('pdf.colPatient'), style: 'th' }, { text: t('pdf.colTask'), style: 'th' }, { text: t('pdf.colDue'), style: 'th', alignment: 'right' }],
          ...g.patients.flatMap((p) => p.tasks.map((task) => [{ text: p.patient, color: INK_2 }, task.title, { text: formatDayMonth(task.due, lang), alignment: 'right' }])),
        ],
      },
      layout: hairlineTable,
      margin: [24, 0, 0, 10], // items sit 24 in from the owner's name, as a sub-list
    } as Content,
  ]);

  const meta =
    meeting.status === 'sent'
      ? t('record.meta', { type, date, n: meeting.durationMin, sent: meeting.sentTo ?? 0, total: meeting.participants.length })
      : t('record.metaUnsent', { type, date, n: meeting.durationMin });

  const doc: TDocumentDefinitions = {
    pageSize: 'A4',
    pageMargins: [48, 56, 48, 56],
    info: { title: `${t('pdf.title')} — ${meetingHeading(meeting, lang)}`, creator: 'Liminal' },
    defaultStyle: { font: 'Roboto', fontSize: 10.5, color: INK, lineHeight: 1.25 },
    styles: {
      plate: { fontSize: 8.5, color: INK_2, characterSpacing: 0.4 },
      h1: { fontSize: 20, bold: true, margin: [0, 2, 0, 2] },
      h2: { fontSize: 12.5, bold: true, margin: [0, 18, 0, 8] },
      owner: { fontSize: 11, bold: true, margin: [0, 4, 0, 4] },
      th: { fontSize: 8.5, color: INK_2 },
      note: { fontSize: 9, color: INK_2 },
    },
    header: () => ({
      columns: [
        { text: 'Liminal', bold: true, fontSize: 9 },
        { text: t('pdf.title'), alignment: 'right', fontSize: 9, color: INK_2 },
      ],
      margin: [48, 24, 48, 0],
    }),
    footer: (page, pages) => ({
      columns: [
        { text: t('pdf.generated', { date: formatFullDate(todayISO(), lang) }), style: 'note' },
        { text: t('pdf.page', { n: page, total: pages }), alignment: 'right', style: 'note' },
      ],
      margin: [48, 16, 48, 0],
    }),
    content: [
      { text: t('pdf.title').toUpperCase(), style: 'plate' },
      { text: meetingHeading(meeting, lang), style: 'h1' },
      { text: meta, style: 'note' },
      { canvas: [{ type: 'line', x1: 0, y1: 0, x2: 499, y2: 0, lineWidth: 0.75, lineColor: HAIRLINE }], margin: [0, 14, 0, 0] },

      // The final MoM holds only the summary and action items (owner, deadline).
      { text: t('review.summary'), style: 'h2' },
      meeting.summary?.length ? { text: summaryProse(meeting.summary), margin: [0, 0, 0, 4] } : { text: t('review.noSummary'), style: 'note' },

      { text: t('mom.actions'), style: 'h2' },
      ...(tasks.length ? tasks : [{ text: t('pdf.noTasks'), style: 'note' } as Content]),
    ],
  };

  return pdfMake.createPdf(doc);
}

/** The attachment's file name, e.g. MoM-Cardiology-board-2026-09-26.pdf */
export const momFileName = (meeting: Meeting) => `MoM-${safeName(meeting.title)}-${meeting.date}.pdf`;

/** Downloads the MoM PDF. */
export async function downloadMomPdf(meeting: Meeting, t: T, lang: Lang) {
  (await buildMomPdf(meeting, t, lang)).download(momFileName(meeting));
}
