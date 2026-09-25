from __future__ import annotations

import json

from .config import settings
from .glossary import llm_term_table
from .local import pick_device, require_local_path
from .schemas import Minutes, Transcript

SYSTEM_PROMPT = """You are an on-premise hospital meeting secretary.
Read a mixed Romanian / Russian / English transcript.
Write the Minutes of Meeting in {language}.
Extract real decisions and action items. Do not invent owners or deadlines.
If a field is unknown, use null.
Normalize medical terms using this glossary (ro | ru | en):
{glossary}
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
"""


class LocalLlm:
    def __init__(self) -> None:
        from llama_cpp import Llama

        gguf = require_local_path(settings.llm_gguf, "LLM GGUF")
        offload = -1 if pick_device(settings.device) == "cuda" else 0
        self.model_id = str(gguf)
        self._llm = Llama(
            model_path=self.model_id,
            n_ctx=settings.llm_ctx,
            n_gpu_layers=offload,
            verbose=False,
        )

    def extract_minutes(self, transcript: Transcript, meeting_type: str, language: str | None = None) -> Minutes:
        language = language or settings.llm_language
        result = self._llm.create_chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT.format(language=language, glossary=llm_term_table()),
                },
                {
                    "role": "user",
                    "content": (
                        f"Meeting type selected by user: {meeting_type}\n\n"
                        f"Transcript:\n{transcript.text}"
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        content = result["choices"][0]["message"]["content"]
        data = json.loads(content)
        data["meeting_type"] = meeting_type
        data["language"] = language
        return Minutes.model_validate(data)
