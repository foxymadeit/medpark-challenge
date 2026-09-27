"""Kaggle T4 entry for asr_train.zeroshot: NeMo models first, then the current Whisper pipeline.

Needs the Medpark recording attached as a dataset (any *.m4a under /kaggle/input).
Push from the repo root:  kaggle kernels push -p asr-llm/scripts/kaggle_asr_zeroshot
Locally, run `python -m asr_train.zeroshot` from asr-llm/ instead.
"""

import os
import subprocess
import sys
from pathlib import Path

BRANCH = "samoilov-asr-llm"
REPO = "/tmp/repo"
ASR = f"{REPO}/asr-llm"


def sh(cmd: str, **kwargs) -> None:
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True, **kwargs)


# What this push runs. The full bench: NEMO = "parakeet,canary,jackrabbit", SETS = "all".
# This push: the fine-tuned Parakeet (medpark-asr-finetune v8 output, attached as a kernel source) on the
# sets it can be compared on against the zero-shot Parakeet of 2026-09-26; rompar is left out (broken references).
NEMO = "parakeet"
SETS = "gold,fleurs_ro,fleurs_ru,fleurs_en,cs_ru_en,cs_ro_en"
FINETUNED = next(Path("/kaggle/input").rglob("parakeet-tdt-0.6b-v3-medpark.nemo"), None)
WHISPER = "large-v3"  # large-v3 (the product's GPU default) | turbo (measured 2026-09-26: 1.4x faster, gold CER 0.54 vs 0.44)
# Whisper settings to time, one bench each (own work dir). {} = the product defaults.
# Measured 2026-09-26 on the hour: beam 5 746 s, beam 1 669 s but gold CER 0.475 vs 0.435. Beam 5 stays.
VARIANTS = {}

sh(f"git clone -q --depth 1 -b {BRANCH} https://github.com/foxymadeit/medpark-challenge {REPO}")
# faster-whisper + pydantic-settings: the cut child uses asr_llm's Silero VAD to split long recordings.
nemo = "'nemo_toolkit[asr]' " if NEMO else ""
sh(f"pip install -q {nemo}huggingface_hub soundfile pyarrow faster-whisper pydantic-settings")
audio = next(Path("/kaggle/input").rglob("*.m4a"))
# The synthetic medical round ships in the repo; its recording script is the reference until someone corrects it by ear.
clip = "--clip synthetic=data/syntethic_record.m4a,data/recording_scripts/medical_round.md"
bench = f"{sys.executable} -m asr_train.zeroshot --sets {SETS} {clip} --audio '{audio}'"
if NEMO:
    model_path = f" --model-path parakeet={FINETUNED}" if FINETUNED else ""
    sh(f"{bench} --work /kaggle/working --models {NEMO}{model_path}", cwd=ASR)
if not VARIANTS:
    sys.exit(0)
# Whisper runs the asr_llm pipeline: its deps and weights come after the NeMo runs. The test sets are reused.
sh(f"pip install -q -e '{ASR}[asr]' && python scripts/fetch_whisper.py {WHISPER}", cwd=ASR)
env = {**os.environ, "MOM_DEVICE": "cuda", "MOM_ASR_COMPUTE_TYPE": "int8_float16",
       "MOM_ASR_MODEL_DIR": "models/whisper" if WHISPER == "large-v3" else "models/whisper-turbo"}
for name, extra in VARIANTS.items():
    work = "/kaggle/working" if name == "beam5" else f"/kaggle/working/{name}"
    sh(f"{bench} --work {work} --models whisper", cwd=ASR, env={**env, **extra})
