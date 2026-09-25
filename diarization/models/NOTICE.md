# Bundled models

These two files ship with the repo so the diarizer runs on a machine that
has never been online. Other embedders are fetched with `diarizer models fetch --all`.

| File | What it does | Origin | License |
|---|---|---|---|
| `segmentation-3.0.onnx` | Who is talking in each 17 ms frame (up to 3 local speakers) | pyannote/segmentation-3.0 by Hervé Bredin, ONNX export by k2-fsa/sherpa-onnx | MIT |
| `wespeaker_en_voxceleb_CAM++_LM.onnx` | Voice embedding (512-d) used to tell people apart | WeSpeaker CAM++ trained on VoxCeleb2, ONNX export by k2-fsa/sherpa-onnx | CC-BY-4.0 |

SHA-256 checksums are pinned in `diarizer/models.py`.
