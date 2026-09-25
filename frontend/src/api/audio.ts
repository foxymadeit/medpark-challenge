import { ApiError } from "./client";
export const MAX_AUDIO_BYTES = 500 * 1024 * 1024;
export const MAX_AUDIO_SECONDS = 3 * 60 * 60;
export function validateAudioFile(file: Pick<File, "name" | "type" | "size">) {
  const ext = file.name.split(".").pop()?.toLowerCase();
  const types: Record<string, string[]> = {
    wav: ["audio/wav", "audio/wave", "audio/x-wav"],
    mp3: ["audio/mpeg", "audio/mp3"],
    m4a: ["audio/mp4", "audio/x-m4a", "video/mp4"],
  };
  if (
    !ext ||
    !types[ext] ||
    file.size <= 0 ||
    file.size > MAX_AUDIO_BYTES ||
    (file.type && !types[ext].includes(file.type))
  )
    throw new ApiError("invalidAudio");
}
export function validateDuration(seconds: number) {
  if (!Number.isFinite(seconds) || seconds <= 0 || seconds > MAX_AUDIO_SECONDS)
    throw new ApiError("invalidAudio");
}
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
      } catch {
        clean();
        reject(new ApiError("invalidAudio"));
      }
    };
    audio.onerror = () => {
      clean();
      reject(new ApiError("invalidAudio"));
    };
    timer = setTimeout(() => {
      clean();
      reject(new ApiError("invalidAudio"));
    }, 15000);
    audio.preload = "metadata";
    audio.src = url;
  });
}
