import { transcriptAlternatives } from '../mocks';
import type { TranscriptLine, TranscriptToken } from '../types';

const TOKEN = /\[\[(.+?)\]\]|[\p{L}\p{N}][\p{L}\p{N}'’-]*|\s+|[^\s\p{L}\p{N}]+/gu;

/** "[[Bed 8]]: I will…" → tokens (lossless: joining the texts gives the plain sentence). */
export function tokenize(text: string): TranscriptToken[] {
  const out: TranscriptToken[] = [];
  for (const m of text.matchAll(TOKEN)) {
    if (m[1] !== undefined) out.push({ kind: 'kw', text: m[1] });
    else if (/^\s+$/.test(m[0])) out.push({ kind: 'space', text: m[0] });
    else if (/[\p{L}\p{N}]/u.test(m[0][0])) out.push({ kind: 'word', text: m[0] });
    else out.push({ kind: 'punct', text: m[0] });
  }
  return out;
}

export const lineTokens = (line: TranscriptLine) => line.tokens ?? tokenize(line.text);

/** MOCK: alternative readings the speech model considered (a real build gets these per word from ASR n-best). */
export function alternativesFor(word: string): string[] {
  return (transcriptAlternatives[word.toLowerCase()] ?? []).filter((a) => a.toLowerCase() !== word.toLowerCase());
}

/** The sentence as plain text (with any corrections applied). */
export const lineText = (line: TranscriptLine) => lineTokens(line).map((t) => t.text).join('');

/** What the AI originally heard, without keyword markup. */
export const originalText = (line: TranscriptLine) => line.text.replace(/\[\[(.+?)\]\]/g, '$1');

/**
 * Re-tokenise an edited sentence, keeping the old highlighted terms highlighted where they still appear
 * (longest first, so "Bed 8" wins over "8").
 */
export function retokenize(text: string, previous: TranscriptToken[]): TranscriptToken[] {
  const kws = [...new Set(previous.filter((t) => t.kind === 'kw').map((t) => t.text))].sort((a, b) => b.length - a.length);
  let marked = text;
  for (const kw of kws) marked = marked.split(kw).join(`[[${kw}]]`).replace(/\[\[\[\[(.+?)\]\]\]\]/g, '[[$1]]');
  return tokenize(marked).map((t) => ({ ...t, fixed: undefined }));
}

/** "00:02:14" → seconds. */
export const atSeconds = (at: string) => at.split(':').map(Number).reduce((a, n) => a * 60 + n, 0);

/** How long a line lasts: until the next one starts (3–30 s; 8 s for the last line). */
export function lineSeconds(lines: TranscriptLine[], i: number): number {
  const next = lines[i + 1];
  const s = next ? atSeconds(next.at) - atSeconds(lines[i].at) : 8;
  return Math.min(30, Math.max(3, s));
}
