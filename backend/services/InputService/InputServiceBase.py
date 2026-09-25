"""Service flow:
1. Receive the user's audio upload.
2. Ingest the audio into an IngestedAudio payload.
3. Send the payload to the downstream service.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from fastapi import UploadFile


@dataclass(frozen=True, slots=True)
class IngestedAudio:
    """Audio data prepared for downstream services."""

    content: bytes
    filename: str | None
    content_type: str | None


class InputServiceBase(ABC):
    """Define the recording ingestion and downstream publishing workflow."""

    async def process(self, audio_file: UploadFile) -> IngestedAudio:
        """Ingest an uploaded recording, then share it with other services."""
        audio = await self.ingest(audio_file)
        await self.share(audio)
        return audio

    @abstractmethod
    async def ingest(self, audio_file: UploadFile) -> IngestedAudio:
        """Read and normalize the uploaded recording."""
        raise NotImplementedError

    @abstractmethod
    async def share(self, audio: IngestedAudio) -> None:
        """Publish the ingested recording to downstream services."""
        raise NotImplementedError