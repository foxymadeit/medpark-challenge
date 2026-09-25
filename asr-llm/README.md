# ASR + local LLM (reference hardware)

Target: **one 16 GB GPU**, or **CPU 32 GB RAM**. Runtime: **no internet**.

Diarization and n8n are other people's slices.

## How the process runs

```
audio (or a ready transcript JSON)
        │
        ▼
 1. ffmpeg → 16 kHz mono
 2. energy VAD → speech spans
 3. pack into ≤15 s batches          ← language-agnostic, no 3-model router
 4. faster-whisper large-v3           ← NO glossary, NO hotwords (v2 settings)
 5. unload Whisper
        │
        ▼
 6. retrieve ~24 glossary rows        ← numpy search over medical_ro_ru_en.json
    that look like this transcript
        │
        ▼
 7. local LLM (GGUF)                  ← summary + action items + term normalize
 8. JSON minutes
```

Whisper never sees the dictionary. The LLM sees a **subset** retrieved from the frozen JSON. Nothing is trained on the Medpark sample.

Two ways in:

- **Full:** audio file → steps 1–8 (needs Whisper weights + GGUF, CUDA if available).
- **Skip ASR:** `--from-transcript transcript_v2.json` → steps 6–8 (needs GGUF only). Use this for the Kaggle v2 text.

`--preview-glossary` stops after step 6: prints the retrieved table, no LLM.

## Models (copy in by hand, or one-time fetch while you still have internet)

```
asr-llm/models/whisper/                         # Systran faster-whisper large-v3
asr-llm/models/llm/qwen2.5-7b-instruct-q4_k_m.gguf
```

```bash
python scripts/fetch_qwen.py    # Qwen/Qwen2.5-7B-Instruct-GGUF, q4_k_m, ~4.7 GB
```

## Canary check (Kaggle T4, not the Mac)

Whisper v2 stays the frozen baseline. Canary-1B-v2 is a second ASR pass on the
same audio. Weights download on Kaggle (Internet ON, GPU T4). Paste
`scripts/kaggle_canary_bench.py` into one cell. It writes
`/kaggle/working/transcript_canary.json` in the same shape as the Whisper bench.
Canary is told `source_lang=ro` (transcribe, not translate); Russian and English
stretches may lose to Whisper.

## Run

```bash
cd asr-llm
pip install -e ".[asr,llm,dev]"

# See which terms the retriever picks (no GPU LLM required)
python -m asr_llm.cli --from-transcript ~/Downloads/transcript_v2.json --preview-glossary

# Minutes from the Kaggle v2 transcript
python -m asr_llm.cli --from-transcript ~/Downloads/transcript_v2.json \
  --meeting-type medical --out /tmp/mom.json

# Full local audio path (slow on M4 CPU, fine on NVIDIA 16 GB)
python -m asr_llm.cli ../data/Medpark_audio.m4a --meeting-type medical --out /tmp/mom.json
```

## Tests

```bash
pytest
```
