#!/usr/bin/env python3
"""One-time setup for MOM_ASR_ENGINE=specialists: copy the three models onto disk. Not imported at runtime.

    pip install "nemo_toolkit[asr]" && pip install --no-deps git+https://github.com/salute-developers/GigaAM
    python scripts/fetch_specialists.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[1] / "models" / "specialists"


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    for repo, name in (("gabrielpirlo/Sped_ParakeetRomanian_110M_TDT-CTC", "SpeD-ParakeetRo_110M_TDT-CTC.nemo"),
                       ("nvidia/parakeet-tdt-0.6b-v3", "parakeet-tdt-0.6b-v3.nemo")):
        shutil.copy(hf_hub_download(repo, name), ROOT / name)
        print("ok", ROOT / name)
    import gigaam

    gigaam.load_model("v3_e2e_rnnt", download_root=str(ROOT / "gigaam"))  # downloads the checkpoint and tokenizer once
    print("ok", ROOT / "gigaam")


if __name__ == "__main__":
    main()
