/**
 * Soft tint palette shared by avatars and template colours.
 * bg + fg pairs are all ≥ 5.7:1; `dot` is a stronger mark for swatches and small badges.
 * Kept apart from the speaker colours, which are reserved for transcript dots and waveforms.
 */
export const PALETTE = {
  rose: { bg: '#fbe3e6', fg: '#8a2a3b', dot: '#d9546c' },
  peach: { bg: '#fde8d7', fg: '#8a4a1c', dot: '#e07b3a' },
  amber: { bg: '#fbf0cf', fg: '#6e5208', dot: '#d6a51c' },
  green: { bg: '#e1f2e4', fg: '#235e33', dot: '#3f9a5a' },
  teal: { bg: '#ddf1f0', fg: '#1c5f5b', dot: '#2b958e' },
  blue: { bg: '#e2ecfd', fg: '#274c8f', dot: '#3b6fd4' },
  violet: { bg: '#ece6fa', fg: '#52408c', dot: '#7a5fc7' },
  stone: { bg: '#efebe4', fg: '#5b544b', dot: '#8f8579' },
  // Templates only: solid ink badge with white icon (not used for avatars).
  ink: { bg: '#101010', fg: '#ffffff', dot: '#101010' },
} as const;

export type ColorKey = keyof typeof PALETTE;
/** Choices in the template colour picker (includes ink). */
export const COLOR_KEYS = Object.keys(PALETTE) as ColorKey[];
/** Colours picked automatically from a name: the soft tints only, never ink. */
const AUTO_KEYS = COLOR_KEYS.filter((k) => k !== 'ink');

/** Same text → same colour everywhere (simple string hash). */
export function colorFor(text: string): ColorKey {
  let h = 0;
  for (const ch of text) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return AUTO_KEYS[h % AUTO_KEYS.length];
}

/** A template's colour: the one picked in the editor, else stable from its name. */
export const templateColor = (t: { name: string; color?: ColorKey }): ColorKey => t.color ?? colorFor(t.name);
