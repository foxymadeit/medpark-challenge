"""Generic transcript cleanup. No phrases from any sample recording."""

from __future__ import annotations

import re

from .schemas import ActionItem, Minutes, SpeechSegment

_MIN_REPEAT_RUN = 3


def _fold(text: str) -> str:
    text = text.casefold().strip()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def collapse_repeat_segments(segments: list[SpeechSegment]) -> list[SpeechSegment]:
    """Keep one segment when the same line is emitted many times in a row.

    A run of two is left alone: people do repeat a word. Three or more is the
    decoder loop both Whisper and Canary produce on long audio.
    """
    if not segments:
        return []
    kept: list[SpeechSegment] = []
    index = 0
    while index < len(segments):
        end = index + 1
        key = _fold(segments[index].text)
        while end < len(segments) and key and _fold(segments[end].text) == key:
            end += 1
        run = segments[index:end]
        if key and len(run) >= _MIN_REPEAT_RUN:
            kept.append(run[0].model_copy(update={"end": run[-1].end}))
        else:
            kept.extend(run)
        index = end
    return kept


def _looks_like_person_name(name: str) -> bool:
    """Two or three capitalized words. A single word is usually a term, not a person."""
    parts = [part for part in name.split() if part]
    if not 2 <= len(parts) <= 3:
        return False
    return all(part[0].isalpha() and part[0].isupper() and part[1:].islower() for part in parts)


def ground_minutes(minutes: Minutes, transcript_text: str) -> Minutes:
    """Drop names and quotes the transcript does not actually contain."""
    haystack = _fold(transcript_text)
    attendees = [
        name
        for name in minutes.attendees
        if _looks_like_person_name(name) and _fold(name) in haystack
    ]
    items: list[ActionItem] = []
    for item in minutes.action_items:
        quote = item.source_quote
        if quote is None or _fold(quote) not in haystack:
            quote = None
        items.append(item.model_copy(update={"source_quote": quote}))
    return minutes.model_copy(update={"attendees": attendees, "action_items": items})
