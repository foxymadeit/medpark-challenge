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
