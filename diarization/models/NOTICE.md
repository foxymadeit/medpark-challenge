# Bundled models

These files ship with the repo so the diarizer runs on a machine that
has never been online. Other embedders are fetched with `diarizer models fetch --all`.

| File | What it does | Origin | License |
|---|---|---|---|
| `segmentation-3.0.onnx` | Who is talking in each 17 ms frame (up to 3 local speakers) | pyannote/segmentation-3.0 by Hervé Bredin, ONNX export by k2-fsa/sherpa-onnx | MIT |
| `segmentation-ft.onnx` | The same segmentation model fine-tuned by us for the close-microphone profile, on AMI far-field meetings (CC BY 4.0) and synthetic Romanian/Russian meetings built from Common Voice 22 (CC0) with OpenSLR 28 room echo (Apache-2.0). Training code: `train/finetune_segmentation.py` | MIT (derived from pyannote/segmentation-3.0) |
| `titanet-small.backend.d64.npz` | Projection applied to voiceprints in the far-microphone profile, trained on 38 AMI training meetings | ours, from AMI (CC BY 4.0) | MIT |
| `nemo_en_titanet_small.onnx` | Voice embedding (192-d) used to tell people apart | NVIDIA NeMo TitaNet-S, ONNX export by k2-fsa/sherpa-onnx | NeMo Toolkit license (Apache-2.0), per the NGC model card |

SHA-256 checksums are pinned in `diarizer/models.py`.
