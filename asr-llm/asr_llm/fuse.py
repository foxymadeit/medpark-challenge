"""Choose or combine per-utterance hypotheses with local LLMs.

`single`: one LLM, only the unclear utterances, several per call.
`debate`: every LLM proposes a transcript for every utterance, then each sees
the others' proposals and revises; the text most of them land on wins.

Both obey one rule enforced in code, not in the prompt: the result must be made
of words from the hypotheses. Whisper forced to Russian *translates* Romanian
into fluent Russian, so "does it read well" is not evidence; the acoustic scores
and the hypothesis words are.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Iterable
from typing import Protocol

from .clean import _fold
from .config import settings
from .retrieve import llm_glossary_for
from .schemas import SpeechSegment

SYSTEM_PROMPT = """You fix speech-recognition output from a hospital meeting in Moldova.
Speakers use Romanian, Russian and English, sometimes switching inside one sentence.
Each utterance comes with several hypotheses: the same audio decoded as different languages or by different engines.
A whisper score is the average log-probability of that decode; closer to 0 means the audio fit that text better.

Rules:
- Build each output ONLY from words that appear in that utterance's hypotheses. Never add, translate or explain.
- A fluent hypothesis is not proof. A forced-Russian decode of Romanian speech comes out as a fluent Russian *translation*,
  often with invented names or places. Such meetings are mostly Romanian with Russian and English words mixed in.
  Prefer the higher score; switch to a lower-scored hypothesis only for the words that clearly belong to that language.
- If the speaker switches language mid-sentence, combine the matching spans from different hypotheses.
- Write each word in its own script: Romanian in Latin with diacritics, Russian in Cyrillic, English in English.
- Use the glossary (ro | ru | en) to recognise medical terms. Do not insert a glossary term that no hypothesis contains.
- If nothing fits, copy the best-scored hypothesis unchanged.

Glossary:
{glossary}

Return ONLY JSON: {{"utterances": [{{"id": int, "text": string, "languages": [string]}}]}}
"""

REVISE_NOTE = """
Other reviewers proposed these texts for the same utterances. Reconsider yours; keep it if you still think it is right:
{others}
"""


class ChatModel(Protocol):
    def chat_json(self, system: str, user: str, max_tokens: int) -> dict: ...

    def close(self) -> None: ...


def is_unclear(seg: SpeechSegment, margin: float, floor: float) -> bool:
    scores = sorted((h.score for h in seg.hypotheses if h.score is not None), reverse=True)
    if len(seg.hypotheses) < 2 or not scores:
        return False
    return (len(scores) > 1 and scores[0] - scores[1] < margin) or scores[0] < floor


def grounded(text: str, seg: SpeechSegment, min_cover: float) -> bool:
    vocab = set(_fold(" ".join(h.text for h in seg.hypotheses)).split())
    tokens = _fold(text).split()
    return bool(tokens) and sum(t in vocab for t in tokens) / len(tokens) >= min_cover


def acoustically_plausible(text: str, seg: SpeechSegment, max_drop: float) -> bool:
    """Reject a wholesale swap to a hypothesis that fit the audio clearly worse.

    Measured on the sample: a 7B model replaced Romanian with the fluent forced-Russian
    translation in 12 of 25 utterances. Mixing spans is allowed; swapping is not.
    """
    scored = [h for h in seg.hypotheses if h.score is not None]
    tokens = set(_fold(text).split())
    if not scored or not tokens:
        return True
    # Same home-language head start the acoustic pick used (asr._biased_score).
    biased = lambda h: h.score + (settings.home_bias if h.language == settings.home_language else 0.0)  # noqa: E731
    share = lambda h: len(tokens & set(_fold(h.text).split())) / len(tokens)  # noqa: E731
    source = max(scored, key=share)
    return share(source) < 0.8 or biased(source) >= max(map(biased, scored)) - max_drop


def render(ids: list[int], segments: list[SpeechSegment]) -> str:
    lines = []
    for i in ids:
        seg = segments[i]
        if i > 0:
            lines.append(f"(context before) {segments[i - 1].text}")
        lines.append(f"id={i} [{seg.start:.1f}-{seg.end:.1f}]{' ' + seg.speaker if seg.speaker else ''}")
        for h in seg.hypotheses:
            score = f" score={h.score:.2f}" if h.score is not None else ""
            lines.append(f"  - {h.source}/{h.language}{score}: {h.text}")
    return "\n".join(lines)


def _proposals(model: ChatModel, ids: list[int], segments: list[SpeechSegment], extra: str = "") -> dict[int, dict]:
    hyps_text = " ".join(h.text for i in ids for h in segments[i].hypotheses)
    system = SYSTEM_PROMPT.format(glossary=llm_glossary_for(hyps_text, k=settings.glossary_k))
    try:
        data = model.chat_json(system, render(ids, segments) + extra, max_tokens=180 * len(ids) + 200)
    except ValueError:
        return {}
    out = {}
    for row in data.get("utterances") or []:
        if isinstance(row, dict) and row.get("id") in ids and isinstance(row.get("text"), str):
            out[row["id"]] = row
    return out


def _apply(seg: SpeechSegment, row: dict | None) -> SpeechSegment:
    if not row or not usable(row["text"], seg):
        return seg
    langs = [lang for lang in row.get("languages") or [] if lang in settings.asr_languages]
    return seg.model_copy(update={"text": row["text"].strip(), "language": "+".join(dict.fromkeys(langs)) or seg.language})


def usable(text: str, seg: SpeechSegment) -> bool:
    return grounded(text, seg, settings.fuse_min_cover) and acoustically_plausible(text, seg, settings.fuse_max_drop)


def _windows(ids: list[int], size: int) -> Iterable[list[int]]:
    for k in range(0, len(ids), size):
        yield ids[k : k + size]


def fuse_single(model: ChatModel, segments: list[SpeechSegment]) -> list[SpeechSegment]:
    ids = [i for i, s in enumerate(segments) if is_unclear(s, settings.fuse_margin, settings.fuse_floor)]
    out = list(segments)
    for window in _windows(ids, settings.fuse_window):
        rows = _proposals(model, window, segments)
        for i in window:
            out[i] = _apply(segments[i], rows.get(i))
    return out


def fuse_debate(
    load_models: list[Callable[[], ChatModel]], segments: list[SpeechSegment], rounds: int = 2, window: int = 1
) -> list[SpeechSegment]:
    """Every utterance, every model, `rounds` rounds. One model in memory at a time."""
    ids = [i for i, s in enumerate(segments) if len(s.hypotheses) >= 2]
    proposals: list[dict[int, dict]] = [{} for _ in load_models]
    for round_no in range(rounds):
        previous = [dict(p) for p in proposals]
        for m, load in enumerate(load_models):
            model = load()
            for chunk in _windows(ids, window):
                extra = ""
                if round_no:
                    others = {
                        i: [p[i]["text"] for k, p in enumerate(previous) if k != m and i in p] for i in chunk
                    }
                    extra = REVISE_NOTE.format(others=json.dumps(others, ensure_ascii=False))
                proposals[m].update(_proposals(model, chunk, segments, extra))
            model.close()
    out = list(segments)
    for i in ids:
        valid = [p[i] for p in proposals if i in p and usable(p[i]["text"], segments[i])]
        if valid:
            votes = Counter(_fold(row["text"]) for row in valid)
            best = votes.most_common(1)[0][0]
            out[i] = _apply(segments[i], next(row for row in valid if _fold(row["text"]) == best))
    return out
