import type { TFunction } from "i18next";
import type { MeetingType } from "../types/meeting";
import { DEMO_MODE, departments, distribution } from "./config";
import { request } from "./client";

/** Recipient addresses per meeting type, from the server's routing table. */
export type Routing = Partial<Record<MeetingType, number>>;

/** The human name of the list a meeting type is sent to ("Medical board"),
 * never the configuration slug. */
export function listName(type: MeetingType, t: TFunction): string {
  return t(`list_${type}`);
}

/** "Sends to the Medical board, 2 recipients"; without a count when the
 * server has not said how many. */
export function routingLine(
  type: MeetingType,
  routing: Routing | undefined,
  t: TFunction,
): string {
  const count = routing?.[type];
  return count
    ? t("routingToCount", { list: listName(type, t), count })
    : t("routingTo", { list: listName(type, t) });
}

function countByType(entries: [string, unknown][]): Routing {
  const out: Routing = {};
  for (const [type, value] of entries) {
    if (!(departments as readonly string[]).includes(type)) continue;
    const n = Array.isArray(value)
      ? value.length
      : typeof value === "number"
        ? value
        : typeof value === "object" && value && "recipients" in value
          ? Number((value as { recipients: unknown }).recipients) || 0
          : typeof value === "string"
            ? value.split(",").filter((a) => a.trim()).length
            : 0;
    if (n > 0) out[type as MeetingType] = n;
  }
  return out;
}

/** The server decides who receives each meeting type. Asks `/routing`;
 * administrators can also read it from `/admin`; otherwise no count. */
export async function getRouting(): Promise<Routing> {
  if (DEMO_MODE)
    return Object.fromEntries(
      departments.map((d) => [d, distribution[d].count]),
    ) as Routing;
  try {
    const table = await request<Record<string, unknown>>("/routing");
    return countByType(Object.entries(table));
  } catch {
    /* not offered by this server; try the admin view */
  }
  try {
    const admin = await request<{
      distributionLists?: { id: string; email?: string; active?: boolean }[];
    }>("/admin");
    return countByType(
      (admin.distributionLists ?? [])
        .filter((l) => l.active !== false)
        .map((l) => [l.id, l.email ?? ""]),
    );
  } catch {
    return {};
  }
}
