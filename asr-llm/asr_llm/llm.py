from __future__ import annotations

import json

from .clean import _fold, ground_minutes
from .config import settings
from .local import pick_device, require_local_path
from .retrieve import llm_glossary_for
from .schemas import Minutes, SpeechSegment, Transcript, format_segments

SYSTEM_PROMPT = """You are an on-premise hospital meeting secretary.
Read a mixed Romanian / Russian / English transcript. It may be one meeting or a ward round with several patients.
Write the Minutes of Meeting in {language}.
Separate patients when the transcript itself distinguishes them. Do not invent a bed, a name, or a diagnosis.
attendees: only personal names that appear in the transcript. If none do, use [].
decisions: only what the speakers agree to do. If none are clear, use [].
action_items.source_quote: a contiguous verbatim span copied from the transcript, or null.
Lines may carry a speaker label (e.g. "Speaker 2") from diarization. An owner is a name from the transcript, or the speaker label of the person who takes the task.
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

MERGE_PROMPT = """These are summaries of consecutive parts of one hospital meeting.
Write one title and one summary (under 120 words) in {language} covering all parts.
Do not add facts that are not in the parts.
Return ONLY valid JSON: {{"title": string, "summary": string}}
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
        """Long meetings go window by window, then merge without asking the LLM for new facts."""
        language = language or settings.llm_language
        texts = [format_segments(w) for w in split_windows(transcript.segments, settings.llm_window_s)]
        parts = [self._extract(text, meeting_type, language) for text in texts or [transcript.text]]
        if len(parts) == 1:
            return parts[0]
        merged = merge_minutes(parts)
        header = self._chat_json(
            MERGE_PROMPT.format(language=language),
            "\n\n".join(f"Part {i + 1}: {p.summary}" for i, p in enumerate(parts)),
            max_tokens=400,
        )
        return merged.model_copy(
            update={"title": header.get("title") or merged.title, "summary": header.get("summary") or merged.summary}
        )

    def _chat_json(self, system: str, user: str, max_tokens: int) -> dict:
        result = self._llm.create_chat_completion(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=max_tokens,
        )
        content = result["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned invalid JSON ({exc})") from exc

    def _extract(self, text: str, meeting_type: str, language: str) -> Minutes:
        data = self._chat_json(
            SYSTEM_PROMPT.format(language=language, glossary=llm_glossary_for(text, k=settings.glossary_k)),
            f"Meeting type selected by user: {meeting_type}\n\nTranscript:\n{text}",
            max_tokens=1200,
        )
        data["meeting_type"] = meeting_type
        data["language"] = language
        return ground_minutes(Minutes.model_validate(data), text)

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


def split_windows(segments: list[SpeechSegment], window_s: float) -> list[list[SpeechSegment]]:
    windows: list[list[SpeechSegment]] = []
    for seg in segments:
        if not windows or seg.start - windows[-1][0].start >= window_s:
            windows.append([])
        windows[-1].append(seg)
    return windows


def merge_minutes(parts: list[Minutes]) -> Minutes:
    """Union of per-window lists, deduped by folded text. Title/summary are replaced by the caller."""

    def uniq(items, key):
        seen: set[str] = set()
        out = []
        for item in items:
            k = _fold(key(item))
            if k and k not in seen:
                seen.add(k)
                out.append(item)
        return out

    return parts[0].model_copy(
        update={
            "summary": " ".join(p.summary for p in parts),
            "attendees": uniq([a for p in parts for a in p.attendees], str),
            "decisions": uniq([d for p in parts for d in p.decisions], str),
            "action_items": uniq([a for p in parts for a in p.action_items], lambda a: a.text),
        }
    )


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
