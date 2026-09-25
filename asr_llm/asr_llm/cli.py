from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Local ASR + minutes extraction")
    parser.add_argument("audio", type=Path)
    parser.add_argument("--meeting-type", default="administrative")
    parser.add_argument("--diarization", type=Path, default=None)
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    result = run_pipeline(
        args.audio,
        meeting_type=args.meeting_type,
        diarization_json=args.diarization,
        skip_llm=args.skip_llm,
    )
    payload = result.model_dump()
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(args.out)
    else:
        print(text)


if __name__ == "__main__":
    main()
