/** After a person settles the flagged items, automatic sending still gets
 * its stop window: "Send automatically when ready" promised that anyone can
 * stop it. With the Liminal backend the server keeps that window
 * (POST /meetings/{id}/send-window); this per-tab copy serves the demo store,
 * which has no scheduler. */
const key = (id: string) => `liminal-send-window-${id}`;

function write(id: string, value: string) {
  try {
    sessionStorage.setItem(key(id), value);
  } catch {
    /* private mode or full: the minutes then wait for Send now */
  }
}

export function openSendWindow(id: string, seconds: number) {
  write(id, new Date(Date.now() + seconds * 1000).toISOString());
}

export function stopSendWindow(id: string) {
  write(id, "stopped");
}

/** The window's end as an ISO time, "stopped", or undefined for none. */
export function readSendWindow(id: string): string | undefined {
  try {
    return sessionStorage.getItem(key(id)) ?? undefined;
  } catch {
    return undefined;
  }
}
