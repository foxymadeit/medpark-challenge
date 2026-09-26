import type { Meeting } from "../types/meeting";
export function invalidMinutes(m: Meeting): boolean {
  return Boolean(
    m.reviewFlags?.length ||
    m.actionItems?.some(
      (a) =>
        !a.task.trim() ||
        !a.ownerParticipantId ||
        !m.participants.some((p) => p.id === a.ownerParticipantId),
    ),
  );
}
