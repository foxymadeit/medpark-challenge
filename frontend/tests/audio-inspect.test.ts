import { afterEach, describe, expect, it, vi } from "vitest";
import { inspectAudio } from "../src/api/audio";

class FakeAudio {
  onloadedmetadata: (() => void) | null = null;
  onerror: (() => void) | null = null;
  duration = 0;
  preload = "";
  removeAttribute() {}
  load() {}
  set src(_: string) {
    queueMicrotask(() => (FakeAudio.decodes ? ((this.duration = 702), this.onloadedmetadata?.()) : this.onerror?.()));
  }
  static decodes = true;
}

describe("inspectAudio", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("reads the length when the browser can decode the file", async () => {
    vi.stubGlobal("Audio", FakeAudio);
    FakeAudio.decodes = true;
    const file = new File([new Uint8Array(10)], "meeting.m4a", { type: "audio/mp4" });
    await expect(inspectAudio(file)).resolves.toBe(702);
  });

  it("lets the server judge a codec this browser cannot play, like ALAC in Medpark's .m4a", async () => {
    vi.stubGlobal("Audio", FakeAudio);
    FakeAudio.decodes = false;
    const file = new File([new Uint8Array(10)], "Medpark_audio.m4a", { type: "audio/mp4" });
    await expect(inspectAudio(file)).resolves.toBe(0);
  });
});
