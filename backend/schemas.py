from typing import Literal

from pydantic import BaseModel, Field

MeetingType = Literal["medical", "executive", "administrative"]


class ActionItem(BaseModel):
	text: str
	owner: str | None = None
	deadline: str | None = None
	source_quote: str | None = None


class Minutes(BaseModel):
	title: str
	meeting_type: MeetingType
	language: str = "ro"
	summary: str
	attendees: list[str] = Field(default_factory=list)
	decisions: list[str] = Field(default_factory=list)
	action_items: list[ActionItem] = Field(default_factory=list)


class EmailSendRequest(BaseModel):
	minutes: Minutes
	participant_emails: list[str] = Field(default_factory=list)


class EmailSendResponse(BaseModel):
	status: Literal["sent", "partial", "failed"]
	accepted_count: int
	refused_count: int
	message: str


class AudioUploadResponse(BaseModel):
	"""Response returned after an audio file is forwarded."""

	message: str
	filename: str | None
	content_type: str | None
	size: int