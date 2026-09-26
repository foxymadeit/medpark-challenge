"""For recording the demo video on a laptop without a GPU: each stage hands
back what the real pipeline produced for the same recording on a 16 GB GPU
(the hour test's work folder for our mock board, minutes/eval/hour_tests), after
a short pause. The video says on screen that the wait is cut.

    LIMINAL_ASR_CMD="python demo/replay_stage.py asr {work}"
    LIMINAL_DIARIZE_CMD="python demo/replay_stage.py diarize {work}"
    LIMINAL_MINUTES_CMD="python demo/replay_stage.py minutes {work}"
    LIMINAL_REPLAY_DIR=/path/to/out/team2
"""
import os
import shutil
import sys
import time
from pathlib import Path

stage, work = sys.argv[1], Path(sys.argv[2])
src = Path(os.environ["LIMINAL_REPLAY_DIR"])
time.sleep(float(os.getenv("LIMINAL_REPLAY_PAUSE_S", "3")))
if stage == "asr":
    shutil.copy(src / "asr.json", work / "asr.json")
elif stage == "diarize":
    shutil.copytree(src / "diarization", work / "diarization", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("*.wav"))
elif stage == "minutes":
    shutil.copytree(src / "minutes", work / "minutes", dirs_exist_ok=True)
else:
    sys.exit(f"unknown stage {stage}")
