from __future__ import annotations

import argparse
import json
from pathlib import Path

from .offline import block_outbound
from .pipeline import run_pipeline


def main() -> None:
    block_outbound()
    parser = argparse.ArgumentParser(description="Local ASR + minutes extraction")
    parser.add_argument("audio", type=Path)
    parser.add_argument("--meeting-type", default="administrative")
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    result = run_pipeline(args.audio, meeting_type=args.meeting_type, skip_llm=args.skip_llm)
    text = json.dumps(result.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(args.out)
    else:
        print(text)


if __name__ == "__main__":
    main()
