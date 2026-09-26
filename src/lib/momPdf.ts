import type { Content, TDocumentDefinitions } from 'pdfmake/interfaces';
import { groupTasks } from '../components/Minutes';
import type { Lang } from '../i18n/I18nProvider';
import type { Meeting } from '../types';
import { formatDayMonth, formatFullDate, todayISO } from './format';
import { lineTokens } from './transcript';

type T = (key: string, vars?: Record<string, string | number>) => string;

// Design tokens (see styles/tokens.css) — ink-primary is the only accent.
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
 * Builds the Minutes of Meeting as a real PDF file and downloads it.
 * pdfmake is lazy-loaded (≈1 MB) so it only costs anything when someone clicks Download.
 * Its bundled Roboto covers Romanian diacritics and Cyrillic.
 */
export async function downloadMomPdf(meeting: Meeting, t: T, lang: Lang) {
  const [{ default: pdfMake }, { default: vfs }] = await Promise.all([import('pdfmake/build/pdfmake'), import('pdfmake/build/vfs_fonts')]);
  pdfMake.vfs = vfs;

  const date = formatFullDate(meeting.date, lang);
  const nameOf = (id: string) => meeting.participants.find((p) => p.personId === id)?.name ?? id;
  const type = t(`types.${meeting.type}`);

  const participants: Content = {
    table: {
      headerRows: 1,
      widths: ['*', '*', '*'],
      body: [
        [t('pdf.colName'), t('pdf.colRole'), t('pdf.colEmail')].map((h) => ({ text: h, style: 'th' })),
        ...meeting.participants.map((p) => [{ text: p.name, bold: true }, p.roleThen || '—', { text: p.email ?? '—', color: INK_2 }]),
      ],
    },
    layout: hairlineTable,
  };

  const tasks: Content[] = groupTasks(meeting.tasks).flatMap((g) => [
    { text: nameOf(g.ownerId), style: 'owner' },
    {
      table: {
        headerRows: 1,
        widths: ['*', 110, 70],
        body: [
          [t('pdf.colTask'), t('pdf.colPatient'), t('pdf.colDue')].map((h) => ({ text: h, style: 'th' })),
          ...g.patients.flatMap((p) => p.tasks.map((task) => [task.title, { text: p.patient, color: INK_2 }, formatDayMonth(task.due, lang)])),
        ],
      },
      layout: hairlineTable,
      margin: [0, 0, 0, 10],
    } as Content,
  ]);

  const transcript: Content[] = meeting.transcript.map((line) => ({
    margin: [0, 0, 0, 8],
    stack: [
      { text: [{ text: `${line.at}  `, color: INK_2, fontSize: 9 }, { text: nameOf(line.speakerId), bold: true }] },
      { text: lineTokens(line).map((tok) => (tok.kind === 'kw' ? { text: tok.text, bold: true } : { text: tok.text })) },
    ],
  }));

  const meta =
    meeting.status === 'sent'
      ? t('record.meta', { type, date, n: meeting.durationMin, sent: meeting.sentTo ?? 0, total: meeting.participants.length })
      : t('record.metaUnsent', { type, date, n: meeting.durationMin });

  const doc: TDocumentDefinitions = {
    pageSize: 'A4',
    pageMargins: [48, 56, 48, 56],
    info: { title: `${t('pdf.title')} — ${meeting.title}`, creator: 'Liminal' },
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
      { text: meeting.title, style: 'h1' },
      { text: meta, style: 'note' },
      { canvas: [{ type: 'line', x1: 0, y1: 0, x2: 499, y2: 0, lineWidth: 0.75, lineColor: HAIRLINE }], margin: [0, 14, 0, 0] },

      { text: t('record.participants'), style: 'h2' },
      participants,
      { text: t('pdf.frozen', { date }), style: 'note', margin: [0, 6, 0, 0] },

      { text: t('review.tasks'), style: 'h2' },
      ...(tasks.length ? tasks : [{ text: t('pdf.noTasks'), style: 'note' } as Content]),

      { text: t('review.transcript'), style: 'h2', pageBreak: 'before' },
      { text: t('review.highlighted'), style: 'note', margin: [0, 0, 0, 10] },
      ...transcript,
    ],
  };

  pdfMake.createPdf(doc).download(`MoM-${safeName(meeting.title)}-${meeting.date}.pdf`);
}
