from __future__ import annotations

import json

from .clean import ground_minutes
from .config import settings
from .local import pick_device, require_local_path
from .retrieve import llm_glossary_for
from .schemas import Minutes, Transcript

SYSTEM_PROMPT = """You are an on-premise hospital meeting secretary.
Read a mixed Romanian / Russian / English transcript. It may be one meeting or a ward round with several patients.
Write the Minutes of Meeting in {language}.
Separate patients when the transcript itself distinguishes them. Do not invent a bed, a name, or a diagnosis.
attendees: only personal names that appear in the transcript. If none do, use [].
decisions: only what the speakers agree to do. If none are clear, use [].
action_items.source_quote: a contiguous verbatim span copied from the transcript, or null.
Do not invent owners or deadlines. If a field is unknown, use null.
Normalize medical terms using this retrieved glossary subset (ro | ru | en).
Do not mention a glossary term unless the transcript supports it.
Keep the summary under 120 words. At most 6 decisions and 6 action items.
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

TRANSLATE_PROMPT = """Translate this hospital minutes JSON into {language}.
Keep the same keys and the same number of decisions and action items.
Do not add facts. Do not drop facts.
Leave personal names unchanged.
Leave every source_quote unchanged.
Leave owner and deadline unchanged.
Return ONLY valid JSON with the same shape.
"""


def _gpu_layers() -> int:
    """Offload when CUDA or a local GPU backend (Metal) is actually present."""
    if settings.device == "cpu":
        return 0
    if pick_device(settings.device) == "cuda":
        return -1
    try:
        from llama_cpp import llama_supports_gpu_offload

        if llama_supports_gpu_offload():
            return -1
    except Exception:
        pass
    return 0


class LocalLlm:
    def __init__(self) -> None:
        from llama_cpp import Llama

        gguf = require_local_path(settings.llm_gguf, "LLM GGUF")
        offload = _gpu_layers()
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
                    "content": SYSTEM_PROMPT.format(
                        language=language,
                        glossary=llm_glossary_for(transcript.text, k=settings.glossary_k),
                    ),
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
            max_tokens=1200,
        )
        content = result["choices"][0]["message"]["content"]
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned invalid JSON ({exc})") from exc
        data["meeting_type"] = meeting_type
        data["language"] = language
        return ground_minutes(Minutes.model_validate(data), transcript.text)

    def translate_minutes(self, minutes: Minutes, language: str) -> Minutes:
        result = self._llm.create_chat_completion(
            messages=[
                {"role": "system", "content": TRANSLATE_PROMPT.format(language=language)},
                {"role": "user", "content": json.dumps(minutes.model_dump(), ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        content = result["choices"][0]["message"]["content"]
        translated = Minutes.model_validate(json.loads(content))
        return lock_translation(minutes, translated, language)


def lock_translation(source: Minutes, translated: Minutes, language: str) -> Minutes:
    """Names, quotes, owners and deadlines stay as extracted. Only prose is translated."""
    items = []
    for index, src in enumerate(source.action_items):
        dst = translated.action_items[index] if index < len(translated.action_items) else src
        items.append(
            dst.model_copy(update={"owner": src.owner, "deadline": src.deadline, "source_quote": src.source_quote})
        )
    decisions = translated.decisions
    if len(decisions) != len(source.decisions):
        decisions = source.decisions
    return translated.model_copy(
        update={
            "meeting_type": source.meeting_type,
            "language": language,
            "attendees": list(source.attendees),
            "decisions": decisions,
            "action_items": items,
        }
    )
