from __future__ import annotations

import json

import httpx

from .config import settings
from .schemas import Minutes, Transcript

SYSTEM_PROMPT = """You are an on-premise hospital meeting secretary.
Read a mixed Romanian / Russian / English transcript.
Write the Minutes of Meeting in {language}.
Extract real decisions and action items. Do not invent owners or deadlines.
If a field is unknown, use null.
Return ONLY valid JSON with this shape:
{{
  "title": string,
  "meeting_type": "medical" | "executive" | "administrative",
  "language": string,
  "summary": string,
  "attendees": [string],
  "decisions": [string],
  "action_items": [
    {{"text": string, "owner": string|null, "deadline": string|null, "source_quote": string|null}}
  ]
}}
Keep medical terms in their standard form (CT, RMN, protocol, consiliu medical).
"""


class LocalLlm:
    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        self.model = model or settings.llm_model
        self.host = (host or settings.ollama_host).rstrip("/")

    def extract_minutes(self, transcript: Transcript, meeting_type: str, language: str | None = None) -> Minutes:
        language = language or settings.llm_language
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.format(language=language)},
                {
                    "role": "user",
                    "content": (
                        f"Meeting type selected by user: {meeting_type}\n\n"
                        f"Transcript:\n{transcript.text}"
                    ),
                },
            ],
        }
        with httpx.Client(timeout=600.0) as client:
            response = client.post(f"{self.host}/api/chat", json=payload)
            response.raise_for_status()
            content = response.json()["message"]["content"]
        data = json.loads(content)
        data["meeting_type"] = meeting_type
        data["language"] = language
        return Minutes.model_validate(data)
