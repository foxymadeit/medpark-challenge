from __future__ import annotations

import argparse
import json
from pathlib import Path

from .llm import LocalLlm
from .offline import block_outbound
from .pipeline import load_transcript, minutes_from_transcript, run_pipeline
from .retrieve import llm_glossary_for
from .schemas import Minutes


def main() -> None:
    block_outbound()
    parser = argparse.ArgumentParser(description="Local ASR + minutes extraction")
    parser.add_argument("audio", type=Path, nargs="?", default=None)
    parser.add_argument("--from-transcript", type=Path, default=None)
    parser.add_argument("--meeting-type", default="medical")
    parser.add_argument("--language", default=None, help="Language of the extracted minutes. Default is MOM_LLM_LANGUAGE (ro).")
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--diarization", type=Path, default=None, help="Diarizer session JSON with speaker turns.")
    parser.add_argument("--preview-glossary", action="store_true")
    parser.add_argument("--from-minutes", type=Path, default=None)
    parser.add_argument("--to-languages", default="")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.from_minutes:
        _translate_minutes(args.from_minutes, args.to_languages, args.out)
        return

    if args.from_transcript:
        transcript = load_transcript(args.from_transcript)
        if args.preview_glossary:
            print(llm_glossary_for(transcript.text))
            return
        if args.to_languages:
            _extract_then_translate(
                args.from_transcript,
                args.meeting_type,
                args.language or "en",
                args.to_languages,
                args.out,
            )
            return
        result = minutes_from_transcript(
            args.from_transcript,
            meeting_type=args.meeting_type,
            language=args.language,
        )
    else:
        if args.audio is None:
            parser.error("pass an audio file, or --from-transcript")
        if args.preview_glossary:
            parser.error("--preview-glossary only works with --from-transcript")
        result = run_pipeline(
            args.audio,
            meeting_type=args.meeting_type,
            skip_llm=args.skip_llm,
            diarization=args.diarization,
        )

    text = json.dumps(result.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(args.out)
    else:
        print(text)


def _extract_then_translate(
    transcript_path: Path,
    meeting_type: str,
    language: str,
    languages: str,
    out: Path | None,
) -> None:
    codes = [code.strip() for code in languages.split(",") if code.strip()]
    if not codes:
        raise SystemExit("pass --to-languages, for example ro,ru")
    transcript = load_transcript(transcript_path)
    llm = LocalLlm()
    minutes = llm.extract_minutes(transcript, meeting_type, language=language)
    payload = {
        "minutes": minutes.model_dump(),
        "translations": {code: llm.translate_minutes(minutes, code).model_dump() for code in codes},
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if out:
        out.write_text(text, encoding="utf-8")
        print(out)
    else:
        print(text)


def _translate_minutes(path: Path, languages: str, out: Path | None) -> None:
    codes = [code.strip() for code in languages.split(",") if code.strip()]
    if not codes:
        raise SystemExit("pass --to-languages, for example en,ru")
    raw = json.loads(path.read_text(encoding="utf-8"))
    payload = raw["minutes"] if isinstance(raw, dict) and "minutes" in raw else raw
    source = Minutes.model_validate(payload)
    llm = LocalLlm()
    translated = {code: llm.translate_minutes(source, code).model_dump() for code in codes}
    text = json.dumps(translated, indent=2, ensure_ascii=False)
    if out:
        out.write_text(text, encoding="utf-8")
        print(out)
    else:
        print(text)


if __name__ == "__main__":
    main()
