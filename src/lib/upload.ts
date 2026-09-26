/** Audio file checks shared by the Upload screen and the New meeting upload card. */
export const ACCEPT = '.wav,.mp3,.m4a,audio/wav,audio/mpeg,audio/mp4,audio/x-m4a';
export const isAudio = (f: File) => /\.(wav|mp3|m4a)$/i.test(f.name) || /^audio\//.test(f.type);

/** Read duration (minutes) from the file's metadata. */
export function readMinutes(file: File): Promise<number> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const audio = new Audio();
    audio.preload = 'metadata';
    audio.onloadedmetadata = () => {
      URL.revokeObjectURL(url);
      resolve(Number.isFinite(audio.duration) ? Math.max(1, Math.round(audio.duration / 60)) : 0);
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(0);
    };
    audio.src = url;
  });
}
