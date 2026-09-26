import { saveDemoSession } from "../src/auth/demoSession";
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useRecorder } from "../src/hooks/useRecorder";
class MockRecorder {
  static isTypeSupported() {
    return true;
  }
  state = "inactive";
  mimeType = "audio/webm";
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  onerror: (() => void) | null = null;
  start() {
    this.state = "recording";
  }
  pause() {
    this.state = "paused";
  }
  resume() {
    this.state = "recording";
  }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({
      data: new Blob(["audio"], { type: this.mimeType }),
    });
    queueMicrotask(() => this.onstop?.());
  }
}
// Steps that cross the fake IndexedDB, a React commit and the microphone grant
// are wall-clock bound: on a loaded 2-core machine they take several seconds,
// so the 1 s default of findBy/waitFor fails before the page has even started.
const SLOW_STEP = { timeout: 10000 };
function setup() {
  const stopTrack = vi.fn();
  const media = { getTracks: () => [{ stop: stopTrack }] };
  const getUserMedia = vi.fn(async () => media);
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia },
  });
  vi.stubGlobal("MediaRecorder", MockRecorder);
  vi.stubGlobal(
    "AudioContext",
    class {
      createAnalyser() {
        return {
          fftSize: 128,
          frequencyBinCount: 64,
          getByteFrequencyData: (a: Uint8Array) => a.fill(30),
        };
      }
      createMediaStreamSource() {
        return { connect: () => {} };
      }
      close() {
        return Promise.resolve();
      }
    },
  );
  return { stopTrack, getUserMedia };
}
describe("MediaRecorder lifecycle", () => {
  it("records, pauses, resumes, saves a blob and releases microphone tracks", async () => {
    const { stopTrack } = setup();
    const { result } = renderHook(() => useRecorder());
    await act(() => result.current.start());
    expect(result.current.state).toBe("recording");
    act(() => result.current.pause());
    expect(result.current.state).toBe("paused");
    act(() => result.current.resume());
    expect(result.current.state).toBe("recording");
    let blob: Blob | undefined;
    await act(async () => {
      blob = (await result.current.stop()).blob;
    });
    expect(blob?.size).toBeGreaterThan(0);
    expect(result.current.state).toBe("stopped");
    expect(stopTrack).toHaveBeenCalled();
  });
  it("saves interrupted recording and closes tracks on navigation", async () => {
    const { stopTrack } = setup();
    const interrupted = vi.fn();
    const { result, unmount } = renderHook(() => useRecorder(interrupted));
    await act(() => result.current.start());
    unmount();
    await waitFor(() => expect(interrupted).toHaveBeenCalled());
    expect(stopTrack).toHaveBeenCalled();
  });
  it("reports microphone denial and unsupported devices with actionable error codes", async () => {
    const { getUserMedia } = setup();
    getUserMedia.mockRejectedValueOnce(new Error("denied"));
    const { result } = renderHook(() => useRecorder());
    await act(() => result.current.start());
    expect(result.current.error).toBe("microphone");
    vi.stubGlobal("MediaRecorder", undefined);
    await act(() => result.current.start());
    expect(result.current.error).toBe("unsupported");
  });
});

it("supports automatic recording inside React StrictMode and recovers after refresh", async () => {
  const { StrictMode } = await import("react");
  const { render, screen, fireEvent } = await import("@testing-library/react");
  const { createMemoryRouter, RouterProvider } =
    await import("react-router-dom");
  const { routes } = await import("../src/router");
  const { default: i18n } = await import("../src/i18n/i18n");
  const { createMeeting, getPeople, getMeeting } =
    await import("../src/api/meetings");
  await i18n.changeLanguage("en");
  setup();
  saveDemoSession();
  const m = await createMeeting({
    title: "Recorder test",
    type: "medical",
    inputMode: "record",
    participants: await getPeople(),
  });
  const router = createMemoryRouter(routes, {
    initialEntries: [`/meetings/${m.id}/record`],
  });
  const view = render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>,
  );
  // Load the meeting, commit, grant the microphone and auto-start.
  await screen.findByRole("button", { name: "Pause" }, SLOW_STEP);
  // The stop button waits for 0.1 s of real recording clock.
  await waitFor(
    () =>
      expect(
        screen
          .getByRole("button", { name: "Stop and write minutes" })
          .hasAttribute("disabled"),
      ).toBe(false),
    SLOW_STEP,
  );
  fireEvent.click(screen.getByRole("button", { name: "Pause" }));
  await screen.findByRole("button", { name: "Resume" });
  fireEvent.click(screen.getByRole("button", { name: "Resume" }));
  await screen.findByRole("button", { name: "Pause" });
  fireEvent.click(
    screen.getByRole("button", { name: "Stop and write minutes" }),
  );
  // Save the audio, update the meeting and open processing on its first stage.
  await screen.findByText("Transcribing", { selector: "strong" }, SLOW_STEP);
  expect((await getMeeting(m.id)).durationSeconds).toBeGreaterThan(0);
  expect((await getMeeting(m.id)).status).toBe("processing");
  view.unmount();
}, 40000); // Three SLOW_STEP waits back to back; the 15 s default would cut them short.
