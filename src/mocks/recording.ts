// MOCKED live-recording signals: diarization (who speaks when) and language detection.
// A real build would get these from the on-prem speech pipeline.
import { YOU_ID } from './people';

/** Speaker turns, looped while recording. `null` = the unmatched "Speaker 4". */
export const diarizationTimeline: { speakerId: string | null; seconds: number }[] = [
  { speakerId: YOU_ID, seconds: 5 },
  { speakerId: 'p-elena', seconds: 3 },
  { speakerId: YOU_ID, seconds: 3 },
  { speakerId: 'p-igor', seconds: 2 },
  { speakerId: 'p-elena', seconds: 3 },
  { speakerId: YOU_ID, seconds: 4 },
  { speakerId: null, seconds: 1 },
  { speakerId: 'p-igor', seconds: 3 },
];

/** Languages detected (i18n keys under `lang.*`); the first is "now speaking". */
export const detectedLanguages = ['ro', 'ru'] as const;

/** Mocked processing duration per step, ms. */
export const processingStepMs = 1800;

/** Mocked upload file used by the "board_audio" example in Figma. */
export const exampleUploadName = 'board_audio_0924.m4a';
