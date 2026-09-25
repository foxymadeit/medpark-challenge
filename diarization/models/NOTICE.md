# Bundled models

These two files ship with the repo so the diarizer runs on a machine that
has never been online. Other embedders are fetched with `diarizer models fetch --all`.

| File | What it does | Origin | License |
|---|---|---|---|
| `segmentation-3.0.onnx` | Who is talking in each 17 ms frame (up to 3 local speakers) | pyannote/segmentation-3.0 by Hervé Bredin, ONNX export by k2-fsa/sherpa-onnx | MIT |
| `nemo_en_titanet_small.onnx` | Voice embedding (192-d) used to tell people apart | NVIDIA NeMo TitaNet-S, ONNX export by k2-fsa/sherpa-onnx | NeMo Toolkit license (Apache-2.0), per the NGC model card |

SHA-256 checksums are pinned in `diarizer/models.py`.
