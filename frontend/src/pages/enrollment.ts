export type EnrollmentState =
  | "pick"
  | "ready"
  | "recording"
  | "checking"
  | "saved"
  | "microphone_blocked"
  | "not_enough_speech"
  | "similar_voice";

export const ENROLLMENT_TARGET_SECONDS = 30;
export const MINIMUM_CLEAR_SPEECH_SECONDS = 20;
export const DEMO_SIMILARITY_PERCENT = 78;

export const clearSpeechSeconds = (seconds: number) =>
  Math.min(ENROLLMENT_TARGET_SECONDS, Math.max(0, Math.floor(seconds)));

export const resultState = (
  seconds: number,
  similar: boolean,
): EnrollmentState =>
  clearSpeechSeconds(seconds) < MINIMUM_CLEAR_SPEECH_SECONDS
    ? "not_enough_speech"
    : similar
      ? "similar_voice"
      : "checking";
