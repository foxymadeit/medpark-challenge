"""The processing queue: transcription and speaker diarization in parallel,
then the minutes. Jobs live in SQLite, so a restart picks up where it left
off: anything that was running goes back to the queue.

Each stage is an external command, set by environment so the server can use
the team's own tools in their own virtual environments:

  LIMINAL_ASR_CMD       python -m asr_llm.cli {audio} --skip-llm --out {work}/asr.json
  LIMINAL_DIARIZE_CMD   diarizer file {audio} --out {work}/diarization --plain
  LIMINAL_MINUTES_CMD   mom report {work}/transcript.json --session {session} --type {type}
                        --date {date} --start {start} --out {work}/minutes
  LIMINAL_RENDER_CMD    mom render {render} --type {type}
                        (the same minutes as another meeting type; no model)

and optionally LIMINAL_ASR_CWD, LIMINAL_DIARIZE_CWD, LIMINAL_MINUTES_CWD, LIMINAL_RENDER_CWD.
Commands are split with shlex and run without a shell; placeholders are
filled per argument, so a path with spaces stays one argument.
"""

import json
import logging
import os
import re
import secrets
import shlex
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import delivery
import hardware
import names
import store
from security import now_iso

log = logging.getLogger("liminal.jobs")

DEFAULT_CMDS = {
    "asr": "python -m asr_llm.cli {audio} --skip-llm --out {work}/asr.json",
    "diarize": "diarizer file {audio} --out {work}/diarization --plain",
    "minutes": "mom report {work}/transcript.json --session {session} --type {type} --date {date} "
               "--start {start} --out {work}/minutes",
    "render": "mom render {render} --type {type}",
}
# seconds of work per second of audio, used only for the ETA shown while processing
ETA = {"asr": 0.12, "diarize": 0.15, "minutes": 0.04}
TIMEOUT_S = int(os.getenv("LIMINAL_STAGE_TIMEOUT_S", str(3 * 3600)))
OFFLINE_ENV = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
               "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1"}


class StageFailed(RuntimeError):
    pass


def work_dir(meeting_id: str) -> Path:
    return store.DATA / "meetings" / meeting_id


def enqueue(meeting_id: str) -> None:
    with store.tx() as con:
        con.execute("DELETE FROM jobs WHERE meeting_id=? AND state IN ('queued','failed','done')", (meeting_id,))
        con.execute("INSERT INTO jobs(meeting_id,state,created_at,updated_at) VALUES(?,?,?,?)",
                    (meeting_id, "queued", time.time(), time.time()))


def queue_position(meeting_id: str) -> int | None:
    """How many meetings are ahead of this one: the one running, then the
    queued ones before it. None when it has no job waiting or running."""
    con = store.db()
    mine = con.execute("SELECT id, state FROM jobs WHERE meeting_id=? AND state IN ('queued','running') "
                       "ORDER BY id DESC LIMIT 1", (meeting_id,)).fetchone()
    if mine is None or mine["state"] == "running":
        return None if mine is None else 0
    return con.execute("SELECT COUNT(*) FROM jobs WHERE meeting_id<>? AND (state='running' OR (state='queued' AND id<?))",
                       (meeting_id, mine["id"])).fetchone()[0]


def recover() -> int:
    """After a restart, jobs that were running go back to the queue."""
    with store.tx() as con:
        return con.execute("UPDATE jobs SET state='queued', updated_at=? WHERE state='running'", (time.time(),)).rowcount


def claim() -> dict | None:
    with store.tx() as con:
        row = con.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY id LIMIT 1").fetchone()
        if not row:
            return None
        con.execute("UPDATE jobs SET state='running', attempts=attempts+1, updated_at=? WHERE id=?", (time.time(), row["id"]))
        return dict(row)


def _finish(job_id: int, state: str) -> None:
    with store.tx() as con:
        con.execute("UPDATE jobs SET state=?, updated_at=? WHERE id=?", (state, time.time(), job_id))


def _command(stage: str, values: dict) -> tuple[list[str], str | None]:
    template = os.getenv(f"LIMINAL_{stage.upper()}_CMD", DEFAULT_CMDS[stage])
    args = [part.format(**values) for part in shlex.split(template)]
    return args, os.getenv(f"LIMINAL_{stage.upper()}_CWD") or None


def run_stage(stage: str, values: dict, logs: Path) -> None:
    _run_args(stage, *_command(stage, values), logs)


def _set_stage(meeting_id: str, stage: str, state: str, progress: int | None = None) -> None:
    def change(m):
        stages = m.setdefault("processingStages", {})
        entry = stages.setdefault(stage, {})
        entry["state"] = state
        entry["startedAt" if state == "running" else "endedAt"] = now_iso()
        if progress is not None:
            m["progress"] = max(m.get("progress", 0), progress)
    store.update("meetings", meeting_id, change)


def process(job: dict) -> None:
    meeting = store.get("meetings", job["meeting_id"])
    if meeting is None:
        _finish(job["id"], "failed")
        return
    work = work_dir(meeting["id"])
    audio = next(work.glob("audio.*"), None)
    seconds = float(meeting.get("durationSeconds") or 0)
    eta = timedelta(seconds=60 + seconds * (max(ETA["asr"], ETA["diarize"]) + ETA["minutes"]))

    def start(m):
        m.update(status="processing", processingState="running", progress=5, processingStages={},
                 processingStartedAt=now_iso(), failureReference=None,
                 processingEndsAt=(datetime.now(timezone.utc) + eta).isoformat(timespec="seconds").replace("+00:00", "Z"))
    store.update("meetings", meeting["id"], start)

    try:
        if audio is None:
            raise StageFailed("no audio")
        values = {"audio": str(audio), "work": str(work), "type": meeting["type"],
                  "date": (meeting.get("startedAt") or meeting["createdAt"])[:10],
                  "start": _local_hhmm(meeting.get("startedAt") or meeting["createdAt"]), "session": ""}

        def stage(name: str, progress: int) -> str | None:
            _set_stage(meeting["id"], name, "running")
            try:
                run_stage(name, values, work / "logs")
            except StageFailed as e:
                _set_stage(meeting["id"], name, "failed")
                return str(e)
            _set_stage(meeting["id"], name, "done", progress)
            return None

        with ThreadPoolExecutor(2) as pool:   # the two models run side by side
            asr_err = pool.submit(stage, "asr", 44)
            diar_err = pool.submit(stage, "diarize", 44)
            if asr_err.result():
                raise StageFailed(asr_err.result())
            diar_problem = diar_err.result()
        if diar_problem:   # speakers are a bonus; minutes still come out, with fewer owners
            log.warning("meeting %s: diarization failed (%s); continuing without speakers", meeting["id"], diar_problem)
        session = next((p for p in sorted((work / "diarization").glob("*.json")) if _has_turns(p)), None)
        segments = transcript_segments(work / "asr.json")
        _write_json(work / "transcript.json", {"segments": segments})
        values["session"] = str(session) if session else ""
        _set_stage(meeting["id"], "minutes", "running", 66)
        args, cwd = _command("minutes", values)
        if not session and "--session" in args:   # drop the flag and its empty value together
            i = args.index("--session")
            del args[i:i + 2]
        _run_args("minutes", args, cwd, work / "logs")
        _set_stage(meeting["id"], "minutes", "done", 90)
        store.update("meetings", meeting["id"], lambda m: apply_results(m, work, session, segments))
        _finish(job["id"], "done")
    except StageFailed as e:
        ref = secrets.token_hex(4).upper()
        log.error("meeting %s processing failed [%s]: %s", meeting["id"], ref, e)   # no transcript text in logs

        def failed(m):
            m.update(status="failed", processingState="failed", failureReference=ref)
        store.update("meetings", meeting["id"], failed)
        _finish(job["id"], "failed")


def _run_args(stage: str, args: list[str], cwd: str | None, logs: Path) -> None:
    logs.mkdir(parents=True, exist_ok=True)
    with open(logs / f"{stage}.log", "w") as out:   # stage logs stay in the meeting's owner-only folder
        os.chmod(logs / f"{stage}.log", 0o600)
        try:
            code = subprocess.run(args, cwd=cwd, stdout=out, stderr=subprocess.STDOUT, timeout=TIMEOUT_S,
                                  env={"LIMINAL_SITE_GLOSSARY": str(store.DATA / "site_glossary.json"),
                                       **os.environ, **hardware.stage_env(), **OFFLINE_ENV}).returncode
        except (OSError, subprocess.TimeoutExpired) as e:
            raise StageFailed(f"{stage}: {type(e).__name__}") from e
    if code != 0:
        raise StageFailed(f"{stage} exited with {code}")


def _local_hhmm(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%H:%M")
    except ValueError:
        return "00:00"


def _has_turns(path: Path) -> bool:
    try:
        return "turns" in json.loads(path.read_text())
    except (OSError, ValueError):
        return False


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(path, 0o600)


def transcript_segments(path: Path) -> list[dict]:
    """The recogniser's segments, whatever wrapper it used: the asr_llm
    PipelineResult ({"transcript": {"segments": ...}}), a bare
    {"segments": ...} or a plain list."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("transcript"), dict):
        data = data["transcript"]
    raw = data.get("segments", []) if isinstance(data, dict) else data
    out = []
    for s in raw if isinstance(raw, list) else []:
        text = str(s.get("text", "")).strip()
        if not text:
            continue
        seg = {"start": float(s.get("start", 0)), "end": float(s.get("end", s.get("start", 0))), "text": text}
        if s.get("language"):
            seg["language"] = s["language"]
        if s.get("speaker"):
            seg["speaker"] = s["speaker"]
        out.append(seg)
    return out


_NUM = re.compile(r"(\d+)\s*$")


def _speaker_turns(session: Path | None) -> list[dict]:
    if not session:
        return []
    return json.loads(session.read_text(encoding="utf-8")).get("turns", [])


def _speaker_for(seg: dict, turns: list[dict]) -> str | None:
    best, overlap = None, 0.0
    for t in turns:
        o = min(seg["end"], t["end"]) - max(seg["start"], t["start"])
        if o > overlap:
            best, overlap = t["speaker"], o
    return best or seg.get("speaker")


def apply_results(m: dict, work: Path, session: Path | None, segments: list[dict]) -> None:
    """Put the pipeline's output into the frontend's Meeting model."""
    turns = _speaker_turns(session)
    # participants: one per detected voice, in order of first turn; staff chosen
    # before the meeting keep their place and can be matched to a voice later
    labels = list(dict.fromkeys(t["speaker"] for t in turns)) or list(
        dict.fromkeys(s["speaker"] for s in segments if s.get("speaker")))
    talk = {}
    for t in turns:
        talk[t["speaker"]] = talk.get(t["speaker"], 0.0) + t["end"] - t["start"]
    participants = [p for p in m.get("participants", []) if not p.get("detected") and not p.get("namedInMinutes")]
    claimed = {p.get("speakerId") for p in participants}
    for slot, label in enumerate(labels, 1):
        if label in claimed:
            continue
        n = _NUM.search(label)
        numbered = n and label.lower().startswith(("speaker", "vorbitor", "участник"))
        # speakerNumber lets the app write "Participantul 3" / "Участник 3"; name is the English fallback
        participants.append({"id": f"{m['id']}-voice-{slot}", "name": f"Participant {n.group(1)}" if numbered else label,
                             "speakerId": label, "speakerSlot": slot, "speakingSeconds": round(talk.get(label, 0.0)),
                             "detected": True, **({"speakerNumber": int(n.group(1))} if numbered else {})})
    for p in participants:   # one voice card per detected speaker, for naming them later
        if p.get("detected") and store.get("clusters", p["id"]) is None:
            store.put("clusters", {"id": p["id"], "meetingId": m["id"], "speakerId": p["speakerId"], "label": p["name"],
                                   "speakingSeconds": p.get("speakingSeconds", 0), "sampleAvailable": False,
                                   "identifiedStaffId": None, "status": "unidentified"})
    by_label = {p.get("speakerId"): p for p in participants}
    by_name = {p["name"].casefold(): p for p in participants}

    def owner_of(owner: str) -> str | None:
        owner = (owner or "").strip()
        if not owner:
            return None
        if owner.casefold() in by_name:
            return by_name[owner.casefold()]["id"]
        n = _NUM.search(owner)
        if n:
            for label, p in by_label.items():
                if label and _NUM.search(label) and _NUM.search(label).group(1) == n.group(1):
                    return p["id"]
        return None

    minutes_dir = minutes_folder(work)
    facts_file = next(minutes_dir.glob("*.facts.json"), None)
    facts = json.loads(facts_file.read_text(encoding="utf-8"))["facts"] if facts_file else []
    kept = [f for f in facts if f.get("status") in ("ok", "confirm")]
    # an owner named in the meeting ("Roman, programează…") who is no voice and no one on the
    # list becomes a participant with that name and no voice, as the minutes' own meeting file does
    for f in kept:
        owner = (f.get("owner") or "").strip()
        if f.get("kind") == "action" and owner and not owner_of(owner) and not names.GENERIC.match(owner):
            p = {"id": f"{m['id']}-named-{len(participants) + 1}", "name": owner[:120],
                 "speakerSlot": len(participants) + 1, "speakingSeconds": 0, "namedInMinutes": True}
            participants.append(p)
            by_name[owner.casefold()] = p
    decisions = [{"id": f["id"], "text": f["text"]} for f in kept if f["kind"] == "decision"]
    actions, confirm = [], []
    for f in kept:
        if f["status"] == "confirm":
            confirm.append({"id": f["id"], "kind": f["kind"], "text": f["text"], "problems": f.get("problems", [])})
        if f["kind"] != "action":
            continue
        owner = owner_of(f.get("owner", ""))
        start = _line_start(f.get("evidence", []), segments)
        item = {"id": f["id"], "task": f["text"], "ownerParticipantId": owner, "deadline": f.get("deadline") or None,
                "completed": False}
        if start is not None:
            item["sourceTimestampSeconds"] = start
        actions.append(item)

    # the minutes read the first 3 minutes and name the meeting type; the type picks
    # who receives the email, so a disagreement waits for a person
    report_file = next(minutes_dir.glob("*.report.json"), None)
    detected = json.loads(report_file.read_text(encoding="utf-8")).get("detected_type") if report_file else None
    if detected in ("medical", "executive", "administrative"):
        m["detectedType"] = detected
        if detected != m["type"]:
            confirm.append({"id": "meeting-type", "kind": "meeting_type", "text": f"Meeting type: {m['type']}",
                            "problems": [f"meeting type sounds like {detected}"], "detectedType": detected,
                            "chosenType": m["type"]})

    export = next(minutes_dir.glob("*.meeting.json"), None)
    exported = json.loads(export.read_text(encoding="utf-8")) if export else {}
    documents = _documents(minutes_dir)
    lang = exported.get("minutesLanguage") if exported.get("minutesLanguage") in SUMMARY_WORDS else _main_language(segments)
    transcript = [{"id": f"seg-{i}", "speakerId": _speaker_for(s, turns), "startSeconds": round(s["start"], 2),
                   "endSeconds": round(s["end"], 2), "text": s["text"],
                   **({"language": s["language"]} if s.get("language") in ("ro", "ru", "en", "mixed") else {})}
                  for i, s in enumerate(segments, 1)]
    m.update(
        participants=participants,
        summary=exported.get("summary") or _summary(facts, lang),
        minutesLanguage=lang,
        decisions=decisions,
        actionItems=actions,
        transcript=transcript,
        speakerTimeline=[{"speakerId": t["speaker"], "startSeconds": t["start"], "endSeconds": t["end"]} for t in turns],
        needsConfirmation=confirm,
        documents=documents,
        processingState="complete",
        progress=100,
    )
    delivery.after_processing(m)


def minutes_folder(work: Path) -> Path:
    """Where the minutes stage left its files: work/minutes, or wherever a remote or custom
    minutes command put them under the meeting's work folder (the first *.facts.json)."""
    default = work / "minutes"
    if next(default.glob("*.facts.json"), None):
        return default
    found = next(iter(sorted(work.rglob("*.facts.json"))), None)
    return found.parent if found else default


def _documents(minutes_dir: Path, meeting_type: str = "") -> dict:
    """{lang: {pdf, docx}} from the minutes folder, only this type's files when given."""
    documents = {}
    for f in sorted(minutes_dir.glob("MoM_*")):
        found = re.search(r"_([a-z]+)_(ro|ru|en)\.(pdf|docx)$", f.name)
        if found and meeting_type in ("", found.group(1)):
            documents.setdefault(found.group(2), {})[found.group(3)] = f.name
    return documents


def rerender(meeting_id: str, meeting_type: str) -> dict | None:
    """Build the documents again as another meeting type from the minutes'
    render file (no model). Returns the new {lang: {pdf, docx}}, or None when
    these minutes have no render file. Raises StageFailed."""
    work = work_dir(meeting_id)
    state = next(minutes_folder(work).glob("*.render.json"), None)
    if state is None:
        return None
    run_stage("render", {"render": str(state), "type": meeting_type, "work": str(work)}, work / "logs")
    documents = _documents(minutes_folder(work), meeting_type)
    if not documents:
        raise StageFailed("render wrote no documents")
    return documents


# the fallback summary, when the minutes have none: words and plural forms per language
SUMMARY_WORDS = {
    "en": ("Topics", ("decision", "decisions"), ("action", "actions")),
    "ro": ("Subiecte", ("decizie", "decizii", "de decizii"), ("acțiune", "acțiuni", "de acțiuni")),
    "ru": ("Темы", ("решение", "решения", "решений"), ("поручение", "поручения", "поручений")),
}


def _plural(n: int, forms: tuple, lang: str) -> str:
    """CLDR plural rules: en one/other, ro one/few/other, ru one/few/many."""
    if lang == "en":
        form = forms[0] if n == 1 else forms[1]
    elif lang == "ro":
        form = forms[0] if n == 1 else forms[1] if n == 0 or 1 <= n % 100 <= 19 else forms[2]
    else:
        form = forms[0] if n % 10 == 1 and n % 100 != 11 else \
            forms[1] if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else forms[2]
    return f"{n} {form}"


def _main_language(segments: list[dict]) -> str:
    spoken = [s["language"] for s in segments if s.get("language") in SUMMARY_WORDS]
    return max(SUMMARY_WORDS, key=spoken.count) if spoken else "ro"


def _summary(facts: list[dict], lang: str = "ro") -> str:
    topics = [f["text"] for f in facts if f["kind"] == "topic" and f.get("status") in ("ok", "confirm")]
    decided = sum(f["kind"] == "decision" and f.get("status") == "ok" for f in facts)
    acts = sum(f["kind"] == "action" and f.get("status") in ("ok", "confirm") for f in facts)
    if not topics:
        return ""
    label, decision, action = SUMMARY_WORDS[lang]
    return f"{label}: {'; '.join(topics)}. {_plural(decided, decision, lang)}, {_plural(acts, action, lang)}."


def _line_start(evidence: list[str], segments: list[dict]) -> float | None:
    """Evidence cites numbered lines (L0001 is the first segment)."""
    for e in evidence:
        m = re.fullmatch(r"L(\d+)", e)
        if m and 0 < int(m.group(1)) <= len(segments):
            return round(segments[int(m.group(1)) - 1]["start"], 1)
    return None


class Worker(threading.Thread):
    """Takes queued jobs one at a time (one GPU, one meeting at a time)."""

    def __init__(self, poll_s: float = 1.0):
        super().__init__(daemon=True, name="liminal-worker")
        self.poll_s, self.stopping = poll_s, threading.Event()

    def run(self):
        recover()
        while not self.stopping.is_set():
            job = claim()
            if job is None:
                self.stopping.wait(self.poll_s)
                continue
            try:
                process(job)
            except Exception:   # never let one bad meeting stop the queue
                ref = secrets.token_hex(4).upper()
                log.exception("job %s crashed [%s]", job["id"], ref)
                store.update("meetings", job["meeting_id"],
                             lambda m: m.update(status="failed", processingState="failed", failureReference=ref))
                _finish(job["id"], "failed")
