import type { Meeting, Participant } from "../types/meeting";
export const seedPeople: Participant[] = [
  {
    id: "ana",
    name: "Dr. Ana Popescu",
    email: "ana.popescu@medpark.local",
    role: "cardiology",
    department: "medical",
    enrolled: true,
    enrollmentKind: "prototype",
  },
  {
    id: "elena",
    name: "Elena Ciobanu",
    email: "elena.ciobanu@medpark.local",
    role: "icu",
    department: "medical",
    enrolled: true,
    enrollmentKind: "prototype",
  },
  {
    id: "igor",
    name: "Dr. Igor Rusu",
    email: "igor.rusu@medpark.local",
    role: "surgery",
    department: "medical",
    enrolled: true,
    enrollmentKind: "prototype",
  },
  {
    id: "victor",
    name: "Victor Munteanu",
    email: "victor.munteanu@medpark.local",
    role: "procurement",
    department: "administrative",
  },
];
export function sampleMinutes(participants: Participant[], duration = 3492) {
  const p = participants;
  const stamp = (seconds: number) =>
    Math.min(seconds, Math.max(0, duration - 1));
  return {
    summary:
      "The board reviewed case 24-09 and agreed on a cardiac MRI before Monday’s surgery. ICU capacity was confirmed pending two beds. The MRI service contract needs a renewal decision.",
    decisions: [
      { id: "d1", text: "Cardiac MRI for bed 12 before Monday’s surgery" },
      { id: "d2", text: "Surgery moves to 10:00 on Monday so ICU can prepare" },
      { id: "d3", text: "MRI contract renewal goes to procurement this week" },
    ],
    actionItems: [
      {
        id: "a1",
        task: "Book the cardiac MRI for bed 12",
        ownerParticipantId: p[0]?.id ?? null,
        deadline: "2026-09-28",
        sourceTimestampSeconds: stamp(724),
        completed: false,
      },
      {
        id: "a2",
        task: "Confirm two ICU beds for Monday",
        ownerParticipantId: p[1]?.id ?? null,
        deadline: "2026-09-25",
        sourceTimestampSeconds: stamp(728),
        completed: false,
      },
      {
        id: "a3",
        task: "Check the MRI contract renewal terms",
        ownerParticipantId: p[3]?.id ?? p[2]?.id ?? null,
        deadline: "2026-09-26",
        sourceTimestampSeconds: stamp(732),
        completed: false,
      },
    ],
    transcript: [
      {
        id: "t1",
        speakerId: p[0]?.id ?? null,
        startSeconds: stamp(724),
        endSeconds: stamp(727),
        text: "Bun, trecem la cazul 24-09. The echo shows reduced ejection fraction, deci avem nevoie de RMN cardiac până luni.",
        language: "mixed" as const,
      },
      {
        id: "t2",
        speakerId: p[1]?.id ?? null,
        startSeconds: stamp(728),
        endSeconds: stamp(730),
        text: "Да, я подтвержу две койки в реанимации на понедельник, dar trebuie să vorbesc cu dr. Rusu.",
        language: "mixed" as const,
      },
      {
        id: "t3",
        speakerId: p[2]?.id ?? null,
        startSeconds: stamp(730),
        endSeconds: stamp(731),
        text: "Confirm. I will move the surgery to 10:00 so the ICU team is ready.",
        language: "en" as const,
      },
      {
        id: "t4",
        speakerId: p[3]?.id ?? null,
        startSeconds: stamp(731),
        endSeconds: stamp(732),
        text: "Pentru achiziții: contractul de RMN expiră la sfârșitul lunii.",
        language: "ro" as const,
      },
      {
        id: "t5",
        speakerId: p[0]?.id ?? null,
        startSeconds: stamp(732),
        endSeconds: stamp(736),
        text: "Okay, Victor, проверь условия контракта, please, până vineri.",
        language: "mixed" as const,
      },
    ],
  };
}
export function seedMeetings(now = Date.now()): Meeting[] {
  const participants = seedPeople.map((p, i) => ({
    ...p,
    speakerId: p.id,
    speakerSlot: i,
    speakingSeconds: [1327, 943, 838, 384][i],
  }));
  const base: Meeting = {
    id: "meeting-001",
    title: "Cardiology board, weekly review",
    type: "medical",
    status: "ready",
    createdAt: new Date(now).toISOString(),
    startedAt: new Date(now - 3492000).toISOString(),
    endedAt: new Date(now).toISOString(),
    inputMode: "record",
    durationSeconds: 3492,
    participants,
    distributionList: ["medical-board"],
    ...sampleMinutes(participants),
    demoGenerated: true,
  };
  return [
    base,
    {
      ...structuredClone(base),
      id: "meeting-002",
      title: "Q4 operating priorities",
      type: "executive",
      status: "sent",
      sentAt: new Date(now - 3600000).toISOString(),
      createdAt: new Date(now - 3600000).toISOString(),
      distributionList: ["executive-team"],
      actionItems: [
        {
          id: "a4",
          task: "Draft the Q4 staffing plan for night shifts",
          ownerParticipantId: "elena",
          deadline: "2026-10-01",
          completed: false,
        },
      ],
      summary: "The team reviewed staffing and equipment priorities.",
      decisions: [{ id: "d4", text: "Prepare the Q4 staffing plan." }],
    },
    {
      ...structuredClone(base),
      id: "meeting-003",
      title: "Procurement and staffing",
      type: "administrative",
      status: "sent",
      sentAt: new Date(now - 7200000).toISOString(),
      createdAt: new Date(now - 7200000).toISOString(),
      distributionList: ["admin-office"],
      actionItems: [
        {
          id: "a5",
          task: "Check the MRI contract renewal terms with procurement",
          ownerParticipantId: "elena",
          deadline: "2026-09-29",
          completed: false,
        },
      ],
    },
    {
      ...structuredClone(base),
      id: "meeting-004",
      title: "Interdisciplinary case review",
      status: "sent",
      sentAt: new Date(now - 86400000).toISOString(),
      createdAt: new Date(now - 86400000).toISOString(),
      actionItems: [
        {
          id: "a6",
          task: "Send the updated sepsis protocol to ward leads",
          ownerParticipantId: "elena",
          deadline: "2026-09-26",
          completed: false,
        },
      ],
    },
    {
      ...structuredClone(base),
      id: "meeting-005",
      title: "Night shift handover",
      status: "stopped",
      createdAt: new Date(now - 172800000).toISOString(),
      actionItems: [],
    },
  ];
}
