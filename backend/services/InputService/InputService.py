from typing import Protocol

from fastapi import UploadFile

from .InputServiceBase import IngestedAudio, InputServiceBase


class AudioConsumer(Protocol):
	"""A downstream service that receives an ingested recording."""

	async def consume(self, audio: IngestedAudio) -> None:
		"""Process an ingested recording."""


class InputService(InputServiceBase):
	"""Ingest uploaded recordings and publish them to downstream consumers."""

	def __init__(self, consumer: AudioConsumer) -> None:
		self._consumer = consumer

	async def ingest(self, audio_file: UploadFile) -> IngestedAudio:
		"""Read the uploaded recording into the downstream payload."""
		content = await audio_file.read()
		if not content:
			raise ValueError("The uploaded audio file is empty.")

		return IngestedAudio(
			content=content,
			filename=audio_file.filename,
			content_type=audio_file.content_type,
		)

	async def share(self, audio: IngestedAudio) -> None:
		"""Deliver the recording to the configured downstream consumer."""
		await self._consumer.consume(audio)
