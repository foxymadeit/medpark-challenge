export const DEMO_MODE = Boolean(
  import.meta.env?.DEV && import.meta.env?.VITE_DEMO_MODE === "true",
);
export const AUTO_COUNTDOWN_SECONDS = 30;
export const AUTO_MODE_AVAILABLE = false;
export const departments = ["medical", "executive", "administrative"] as const;
export const distribution = {
  medical: { list: "medical-board", count: 12 },
  executive: { list: "executive-team", count: 7 },
  administrative: { list: "admin-office", count: 9 },
};
