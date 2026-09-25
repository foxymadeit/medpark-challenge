import logging

from fastapi import File, FastAPI, HTTPException, UploadFile

from schemas import AudioUploadResponse
from services.InputService.InputService import InputService
from services.InputService.InputServiceBase import IngestedAudio

app = FastAPI()
logger = logging.getLogger(__name__)


class DownstreamService:
    """Replace this with the service that processes the uploaded audio."""

    async def consume(self, audio: IngestedAudio) -> None:
        logger.info("Received audio for downstream processing: %s", audio.filename)


input_service = InputService(consumer=DownstreamService())

@app.get("/")
def root():
    return {"message": "backend initialized."}


@app.post("/audio", response_model=AudioUploadResponse)
async def upload_audio(file: UploadFile = File(...)) -> AudioUploadResponse:
    """Receive an audio recording and forward it to the downstream service."""
    try:
        audio = await input_service.process(file)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return AudioUploadResponse(
        message="Audio received and forwarded.",
        filename=audio.filename,
        content_type=audio.content_type,
        size=len(audio.content),
    )