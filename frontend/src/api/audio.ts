import { ApiError } from "./client";
export const MAX_AUDIO_BYTES = 500 * 1024 * 1024;
export const MAX_AUDIO_SECONDS = 3 * 60 * 60;
/** What the file picker offers: the four formats the pipeline reads. */
export const AUDIO_ACCEPT =
  ".wav,.mp3,.m4a,.flac,audio/wav,audio/mpeg,audio/mp4,audio/flac,audio/x-flac";
export function validateAudioFile(file: Pick<File, "name" | "type" | "size">) {
  const ext = file.name.split(".").pop()?.toLowerCase();
  const types: Record<string, string[]> = {
    wav: ["audio/wav", "audio/wave", "audio/x-wav"],
    mp3: ["audio/mpeg", "audio/mp3"],
    m4a: ["audio/mp4", "audio/x-m4a", "video/mp4"],
    flac: ["audio/flac", "audio/x-flac"],
  };
  if (!ext || !types[ext] || (file.type && !types[ext].includes(file.type)))
    throw new ApiError("unsupportedAudioType");
  if (file.size <= 0) throw new ApiError("audioEmpty");
  if (file.size > MAX_AUDIO_BYTES) throw new ApiError("audioTooLarge");
}
export function validateDuration(seconds: number) {
  if (!Number.isFinite(seconds) || seconds <= 0)
    throw new ApiError("audioUnreadable");
  if (seconds > MAX_AUDIO_SECONDS) throw new ApiError("audioTooLong");
}
/** Duration in seconds, or 0 when this browser cannot decode the codec (Chrome
 * cannot play ALAC, which is how Medpark's own .m4a sample is encoded). The
 * server measures and checks every upload with ffprobe, so an unknown length
 * here does not block the upload; a damaged file is still refused there. */
export async function inspectAudio(file: File): Promise<number> {
  validateAudioFile(file);
  return new Promise((resolve, reject) => {
    const audio = new Audio();
    const url = URL.createObjectURL(file);
    let timer: ReturnType<typeof setTimeout>;
    const clean = () => {
      clearTimeout(timer);
      audio.removeAttribute("src");
      audio.load();
      URL.revokeObjectURL(url);
    };
    audio.onloadedmetadata = () => {
      const duration = audio.duration;
      try {
        validateDuration(duration);
        clean();
        resolve(duration);
      } catch (error) {
        clean();
        reject(error);
      }
    };
    audio.onerror = () => {
      clean();
      resolve(0);
    };
    timer = setTimeout(() => {
      clean();
      resolve(0);
    }, 15000);
    audio.preload = "metadata";
    audio.src = url;
  });
}
