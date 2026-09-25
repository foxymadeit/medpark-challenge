from __future__ import annotations

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


@app.post("/minutes")
async def minutes(
    audio: UploadFile = File(...),
    meeting_type: MeetingType = Form("administrative"),
    skip_llm: bool = Form(False),
):
    if not audio.filename:
        raise HTTPException(400, "audio file required")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / Path(audio.filename).name
    dest.write_bytes(await audio.read())
    result = run_pipeline(dest, meeting_type=meeting_type, skip_llm=skip_llm)
    return JSONResponse(result.model_dump())
