from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from .offline import block_outbound
from .pipeline import run_pipeline
from .schemas import MeetingType

block_outbound()

app = FastAPI(title="Medpark ASR+LLM", version="0.1.0")
UPLOAD_DIR = Path("/tmp/medpark-asr")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "offline": True}


# Plain `def`: FastAPI runs it in a worker thread, so /health answers during a job.
@app.post("/minutes")
def minutes(
    audio: UploadFile = File(...),
    meeting_type: MeetingType = Form("administrative"),
    skip_llm: bool = Form(False),
    diarization: UploadFile | None = File(None),
):
    if not audio.filename:
        raise HTTPException(400, "audio file required")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{Path(audio.filename).suffix}"
    dest.write_bytes(audio.file.read())
    turns = None
    if diarization is not None:
        turns = dest.with_suffix(".turns.json")
        turns.write_bytes(diarization.file.read())
    result = run_pipeline(dest, meeting_type=meeting_type, skip_llm=skip_llm, diarization=turns)
    return JSONResponse(result.model_dump())
