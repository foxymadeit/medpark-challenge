from pydantic import BaseModel


class AudioUploadResponse(BaseModel):
	"""Response returned after an audio file is forwarded."""

	message: str
	filename: str | None
	content_type: str | None
	size: int