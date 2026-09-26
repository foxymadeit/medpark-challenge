"""ASR by language specialists (MOM_ASR_ENGINE=specialists): SpeD-RoASR for Romanian,
GigaAM-v3 for Russian, Parakeet-TDT v3 for English, combined by asr_llm/ensemble.py.

Weights are local files fetched once at setup (scripts/fetch_specialists.py); nothing is
downloaded at meeting time. Same interface as WhisperAsr, so the pipeline does not change.
"""

from __future__ import annotations

import gc
import tempfile
from pathlib import Path

import numpy as np

from .config import settings
from .ensemble import Word, combine
from .local import pick_device, require_local_path
from .schemas import Hypothesis


def _words(text: str, stamps: list, start: float, end: float) -> list[Word]:
    if stamps:
        return [Word(start + s, start + e, w) for s, e, w in stamps]
    parts = text.split()
    step = (end - start) / max(len(parts), 1)
    return [Word(start + k * step, start + (k + 1) * step, w) for k, w in enumerate(parts)]


class SpecialistAsr:
    def __init__(self) -> None:
        import torch
        from nemo.collections.asr.models import ASRModel
        import gigaam

        self.device = pick_device(settings.device)
        dev = torch.device("cuda:0" if self.device == "cuda" else "cpu")
        self.model_id = "specialists: sped-ro + gigaam-v3 + parakeet-v3"
        self._nemo = {
            "sped": ASRModel.restore_from(str(require_local_path(settings.sped_model, "SpeD-RoASR .nemo")), map_location=dev).eval(),
            "parakeet": ASRModel.restore_from(str(require_local_path(settings.parakeet_model, "Parakeet v3 .nemo")), map_location=dev).eval(),
        }
        root = require_local_path(settings.gigaam_dir, "GigaAM weights dir")
        self._gigaam = gigaam.load_model("v3_e2e_rnnt", device=str(dev), download_root=str(root))
        self._tmp = Path(tempfile.mkdtemp(prefix="asr-"))

    def _nemo_words(self, name: str, path: str, dur: float) -> list[Word]:
        hyp = self._nemo[name].transcribe([path], batch_size=1, timestamps=True, verbose=False)
        hyp = hyp[0] if not isinstance(hyp, tuple) else hyp[0][0]
        hyp = hyp[0] if isinstance(hyp, list) else hyp
        stamps = [(w["start"], w["end"], w["word"]) for w in (getattr(hyp, "timestamp", None) or {}).get("word", []) if "start" in w]
        return _words(getattr(hyp, "text", str(hyp)), stamps, 0.0, dur)

    def transcribe_batch(self, samples: np.ndarray, prev_lang: str | None = None) -> tuple[str, str | None, list[Hypothesis]]:
        import soundfile as sf

        path = self._tmp / "utt.wav"
        sf.write(path, samples.astype(np.float32), settings.sample_rate)
        dur = samples.size / settings.sample_rate
        r = self._gigaam.transcribe(str(path), word_timestamps=True)
        hyps = {
            "sped": self._nemo_words("sped", str(path), dur),
            "gigaam": _words(getattr(r, "text", "") or "", [(w.start, w.end, w.text) for w in getattr(r, "words", None) or []], 0.0, dur),
            "parakeet": self._nemo_words("parakeet", str(path), dur),
        }
        out = combine(hyps, home=settings.home_language)
        hypotheses = [Hypothesis(language=out["language"] or "ro", text=" ".join(w.text for w in ws), source=name)
                      for name, ws in hyps.items() if ws]
        return out["text"], out["language"], hypotheses

    def close(self) -> None:
        self._nemo, self._gigaam = {}, None
        gc.collect()
