export const DEMO_MODE = Boolean(
  import.meta.env?.DEV && import.meta.env?.VITE_DEMO_MODE === "true",
);
const countdown = Number(
  import.meta.env?.VITE_DEMO_SEND_COUNTDOWN_SECONDS ?? 300,
);
export const SEND_COUNTDOWN_SECONDS =
  Number.isFinite(countdown) && countdown > 0 ? countdown : 300;
export const departments = ["medical", "executive", "administrative"] as const;
export const distribution = {
  medical: { list: "medical-board", count: 12 },
  executive: { list: "executive-team", count: 7 },
  administrative: { list: "admin-office", count: 9 },
};
