"""Whole-file baseline: sherpa-onnx offline diarization (segmentation +
embeddings + agglomerative clustering over the entire meeting). It sees
everything before deciding, so it shows how much a global pass could add
on top of the streaming engine.

  python -m eval.offline_baseline --meetings ES2011a IS1008a --threshold 0.5
"""

import argparse
import time

import sherpa_onnx

from diarizer import models
from diarizer.audio import load
from diarizer.neural import SR

from .der import der, read_rttm
from .run_eval import DATA, audio_path, crop, read_uem


def run(meeting, kind, embedder, threshold, num_speakers):
    cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=str(models.model_path(models.SEGMENTATION))), num_threads=2),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=str(models.embedder_path(embedder)), num_threads=2),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=num_speakers, threshold=threshold),
        min_duration_on=0.3, min_duration_off=0.5)
    sd = sherpa_onnx.OfflineSpeakerDiarization(cfg)
    audio = load(audio_path(meeting, kind))
    t = time.perf_counter()
    segs = sd.process(audio).sort_by_start_time()
    rtf = (time.perf_counter() - t) / (len(audio) / SR)
    hyp = [(str(s.speaker), s.start, s.end) for s in segs]
    uem = read_uem(meeting)
    return der(crop(read_rttm(DATA / f"{meeting}.rttm"), uem), crop(hyp, uem)), rtf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meetings", nargs="+", default=["ES2011a", "IS1008a"])
    ap.add_argument("--kind", default="Array1-01")
    ap.add_argument("--embedder", default="campp")
    ap.add_argument("--threshold", type=float, nargs="+", default=[0.5])
    ap.add_argument("--num-speakers", type=int, default=-1)
    a = ap.parse_args()
    for th in a.threshold:
        for m in a.meetings:
            r, rtf = run(m, a.kind, a.embedder, th, a.num_speakers)
            print(f"th {th:.2f} {m:8s} DER {r['der']:.3f} miss {r['miss']:.3f} FA {r['false_alarm']:.3f} "
                  f"conf {r['confusion']:.3f} spk {r['hyp_speakers']}/{r['ref_speakers']} RTF {rtf:.3f}", flush=True)


if __name__ == "__main__":
    main()
