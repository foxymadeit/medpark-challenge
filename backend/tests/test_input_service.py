import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from services.InputService.InputService import InputService
from services.InputService.InputServiceBase import IngestedAudio


class FakeUpload:
    def __init__(self, content: bytes, filename: str, content_type: str) -> None:
        self._content = content
        self.filename = filename
        self.content_type = content_type

    async def read(self) -> bytes:
        return self._content


class InputServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_process_ingests_and_shares_audio_once(self) -> None:
        consumer = AsyncMock()
        service = InputService(consumer=consumer)
        upload = FakeUpload(b"voice data", "recording.webm", "audio/webm")

        result = await service.process(upload)

        expected_audio = IngestedAudio(
            content=b"voice data",
            filename="recording.webm",
            content_type="audio/webm",
        )
        self.assertEqual(result, expected_audio)
        consumer.consume.assert_awaited_once_with(expected_audio)

    async def test_ingest_preserves_upload_metadata(self) -> None:
        consumer = AsyncMock()
        service = InputService(consumer=consumer)
        upload = FakeUpload(b"voice data", "voice.wav", "audio/wav")

        result = await service.ingest(upload)

        self.assertEqual(result.content, b"voice data")
        self.assertEqual(result.filename, "voice.wav")
        self.assertEqual(result.content_type, "audio/wav")

    async def test_process_rejects_empty_audio_and_does_not_share(self) -> None:
        consumer = AsyncMock()
        service = InputService(consumer=consumer)
        upload = SimpleNamespace(
            read=AsyncMock(return_value=b""),
            filename="empty.webm",
            content_type="audio/webm",
        )

        with self.assertRaisesRegex(ValueError, "uploaded audio file is empty"):
            await service.process(upload)

        consumer.consume.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
