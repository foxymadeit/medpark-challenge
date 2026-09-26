// A stand-in for the Liminal backend that follows API_CONTRACT.md closely
// enough to drive the real-mode frontend end to end. It serves the built app
// from dist/ and keeps all state in memory. Test use only.
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { randomUUID } from "node:crypto";

const DIST = new URL("../../dist/", import.meta.url).pathname;
const PORT = Number(process.env.PORT ?? 4173);
const SEND_WINDOW = Number(process.env.SEND_WINDOW ?? 4);
const STEP_MS = Number(process.env.STEP_MS ?? 700);
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".woff2": "font/woff2" };
const USER = { id: "u1", email: "admin@medpark.local", name: "Administrator", role: "admin", initials: "AD" };
const STAGES = ["transcribe", "speakers", "extract", "verify", "write", "render"];
const meetings = new Map();
let session = null;

const iso = (ms = 0) => new Date(Date.now() + ms).toISOString();
function send(res, status, body, headers = {}) {
  const json = body === undefined ? "" : JSON.stringify(body);
  res.writeHead(status, { "Content-Type": "application/json", ...headers });
  res.end(json);
}
async function body(req) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  const raw = Buffer.concat(chunks);
  return (req.headers["content-type"] ?? "").includes("json") && raw.length ? JSON.parse(raw) : raw;
}

// Processing advances one stage per STEP_MS. Shapes follow the real backend
// (romans-branch backend/README.md): processingStages as a map,
// needsConfirmation items that disappear once settled, documents by language.
const STAGE_KEYS = ["asr", "diarize", "minutes"];
function tick(m) {
  if (m.status !== "processing") return m;
  const step = Math.floor((Date.now() - Date.parse(m.processingStartedAt)) / STEP_MS);
  m.processingStages = Object.fromEntries(
    STAGE_KEYS.slice(0, step + 1).map((key, i) => [
      key,
      i < step ? { state: "done", endedAt: iso(-(step - i) * STEP_MS) } : { state: "running", startedAt: iso() },
    ]),
  );
  m.progress = Math.min(100, (100 * step) / STAGE_KEYS.length);
  if (step >= STAGE_KEYS.length) finish(m);
  return m;
}
function finish(m) {
  Object.assign(m, {
    status: "ready",
    processingState: "complete",
    reviewState: "needs_review",
    progress: 100,
    sendWindowSeconds: SEND_WINDOW,
    summary: "The board agreed a cardiac MRI before Monday's procedure.",
    decisions: [{ id: "D1", text: "Cardiac MRI before Monday's procedure" }],
    actionItems: [{ id: "A1", task: "Book the cardiac MRI", ownerParticipantId: "p1", deadline: "2026-09-28", completed: false, sourceTimestampSeconds: 184 }],
    participants: [
      { id: "p1", name: "Participant 1", speakerId: "S1", speakerSlot: 0, speakingSeconds: 1420 },
      { id: "p2", name: "Participant 2", speakerId: "S2", speakerSlot: 1, speakingSeconds: 980 },
    ],
    needsConfirmation: m.type === "medical" ? [{ id: "A2", kind: "action", text: "Order new leads.", problems: ["action without an owner"] }] : [],
    minutesByLanguage: {
      en: { summary: "The board agreed a cardiac MRI before Monday's procedure.", decisions: [{ id: "D1", text: "Cardiac MRI before Monday's procedure" }], actionItems: [{ id: "A1", task: "Book the cardiac MRI" }] },
      ro: { summary: "Consiliul a aprobat o RMN cardiacă înainte de intervenția de luni.", decisions: [{ id: "D1", text: "RMN cardiacă înainte de intervenția de luni" }], actionItems: [{ id: "A1", task: "Programează RMN cardiacă" }] },
      ru: { summary: "Совет одобрил МРТ сердца до вмешательства в понедельник.", decisions: [{ id: "D1", text: "МРТ сердца до вмешательства в понедельник" }], actionItems: [{ id: "A1", task: "Записать на МРТ сердца" }] },
    },
    documents: Object.fromEntries(["ro", "ru", "en"].map((l) => [l, { pdf: `MoM_${l}.pdf`, docx: `MoM_${l}.docx` }])),
    checked: { verified: 11, total: 12 },
  });
  if (m.sendMode === "auto" && !m.needsConfirmation.length) startCountdown(m);
}
function startCountdown(m) {
  Object.assign(m, { status: "sending_soon", deliveryState: "scheduled", reviewState: "reviewed", sendScheduledAt: iso(SEND_WINDOW * 1000), sendWindowSeconds: SEND_WINDOW });
}
function settle(m) {
  if (m.status === "sending_soon" && Date.parse(m.sendScheduledAt) <= Date.now()) {
    Object.assign(m, { status: "sent", deliveryState: "sent", sentAt: iso(), sendScheduledAt: null });
  }
  return tick(m);
}

const routes = [
  ["POST", /^\/api\/auth\/login$/, async (req, res) => {
    const b = await body(req);
    if (b.email !== USER.email || b.password !== "correct horse battery") return send(res, 401, { error: "invalid" });
    session = randomUUID();
    send(res, 200, USER, { "Set-Cookie": `sid=${session}; HttpOnly; SameSite=Strict; Path=/` });
  }],
  ["GET", /^\/api\/auth\/me$/, (req, res) => (session && req.headers.cookie?.includes(session) ? send(res, 200, USER) : send(res, 401, {}))],
  ["POST", /^\/api\/auth\/logout$/, (req, res) => { session = null; send(res, 204); }],
  ["GET", /^\/api\/capabilities$/, (req, res) => send(res, 200, { autoModeAvailable: true })],
  ["GET", /^\/api\/system$/, (req, res) => send(res, 200, { local: true, host: "liminal-test", services: ["asr", "speakers", "automation", "mail", "storage"].map((id) => ({ id, available: true })), capabilities: { autoModeAvailable: true } })],
  ["GET", /^\/api\/(people|templates|voice-profiles|speaker-clusters|action-items)$/, (req, res) => send(res, 200, [])],
  ["GET", /^\/api\/meetings$/, (req, res) => send(res, 200, [...meetings.values()].map(settle))],
  ["POST", /^\/api\/meetings$/, async (req, res) => {
    const b = await body(req);
    const m = { ...b, id: randomUUID(), status: "draft", reviewState: "not_ready", sendMode: b.sendMode ?? "manual", createdAt: iso(), participants: [], distributionList: [`${b.type}-board`] };
    meetings.set(m.id, m);
    send(res, 201, m);
  }],
  ["POST", /^\/api\/meetings\/([^/]+)\/upload$/, async (req, res, id) => {
    await body(req);
    Object.assign(meetings.get(id), { status: "uploaded", audioFilename: "meeting.wav", durationSeconds: 3600 });
    send(res, 204);
  }],
  ["POST", /^\/api\/meetings\/([^/]+)\/process$/, (req, res, id) => {
    const m = meetings.get(id);
    Object.assign(m, { status: "processing", processingState: "running", processingStartedAt: iso(), processingEndsAt: iso(STAGES.length * STEP_MS) });
    send(res, 200, tick(m));
  }],
  ["GET", /^\/api\/meetings\/([^/]+)(\/processing|\/minutes)?$/, (req, res, id) => (meetings.has(id) ? send(res, 200, settle(meetings.get(id))) : send(res, 404, {}))],
  ["POST", /^\/api\/meetings\/([^/]+)\/confirmations\/([^/]+)$/, async (req, res, id, item) => {
    const b = await body(req);
    const m = meetings.get(id);
    if (!["keep", "remove"].includes(b.action)) return send(res, 422, { error: "Use keep or remove." });
    if (b.action === "remove") m.actionItems = m.actionItems.filter((a) => a.id !== item);
    m.needsConfirmation = m.needsConfirmation.filter((c) => c.id !== item);
    send(res, 200, m);
  }],
  ["POST", /^\/api\/meetings\/([^/]+)\/review$/, (req, res, id) => {
    const m = meetings.get(id);
    if (m.needsConfirmation?.length) return send(res, 409, { error: "unresolved" });
    m.reviewState = "reviewed";
    send(res, 200, m);
  }],
  ["POST", /^\/api\/meetings\/([^/]+)\/stop-send$/, (req, res, id) => {
    const m = meetings.get(id);
    Object.assign(m, { status: "ready", sendMode: "manual", deliveryState: "stopped", sendScheduledAt: null, reviewState: "needs_review" });
    send(res, 200, m);
  }],
  ["POST", /^\/api\/meetings\/([^/]+)\/send$/, (req, res, id) => {
    const m = meetings.get(id);
    Object.assign(m, { status: "sent", deliveryState: "sent", sentAt: m.sentAt ?? iso(), sendScheduledAt: null });
    send(res, 200, m);
  }],
  ["GET", /^\/api\/meetings\/([^/]+)\/transcript$/, (req, res) => send(res, 200, [])],
  ["GET", /^\/api\/meetings\/([^/]+)\/documents\/(ro|ru|en)\.(pdf|docx)$/, (req, res, id, lang, kind) => {
    res.writeHead(200, { "Content-Type": kind === "pdf" ? "application/pdf" : "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Content-Disposition": `attachment; filename="MoM_${lang}.${kind}"` });
    res.end(kind === "pdf" ? "%PDF-1.4\n%%EOF" : "PK");
  }],
];

createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  if (url.pathname.startsWith("/api/")) {
    if (req.method !== "GET" && req.headers["x-requested-with"] !== "Liminal") return send(res, 403, { error: "csrf" });
    for (const [method, re, handler] of routes) {
      const match = req.method === method && url.pathname.match(re);
      if (match) return handler(req, res, ...match.slice(1));
    }
    return send(res, 404, { error: "not found" });
  }
  const file = normalize(join(DIST, url.pathname));
  const target = file.startsWith(DIST) && extname(file) ? file : join(DIST, "index.html");
  try {
    const data = await readFile(target);
    res.writeHead(200, { "Content-Type": TYPES[extname(target)] ?? "application/octet-stream" });
    res.end(data);
  } catch {
    res.writeHead(404).end();
  }
}).listen(PORT, "127.0.0.1", () => console.log(`mock backend on http://127.0.0.1:${PORT}`));
