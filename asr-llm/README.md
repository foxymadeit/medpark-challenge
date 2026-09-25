# ASR + local LLM (reference hardware)

Target machine from the brief: **one 16 GB GPU**, or **CPU-only 32 GB RAM**.

**No internet, ever.** Nothing in this package downloads anything — not at runtime, not on first run. Model files are copied into `models/` by hand (USB stick or an internal mirror). If a file is missing, the pipeline stops with an error instead of reaching for a hub.

This package does not do diarization or n8n.

## How offline is enforced

- `enforce_offline()` runs on import and pins `HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE`, so the model libraries never treat a path as a repo id.
- `block_outbound()` runs in the CLI and the API: any non-loopback connection raises `OSError`.
- `require_local_path()` refuses to start unless the weights are already on disk.
- `tests/test_offline.py` blocks sockets and proves the pipeline helpers still work.

## Two pieces

1. `transcribe_audio` — VAD → 30s batches → faster-whisper from `models/whisper/`
2. `write_minutes` — llama.cpp GGUF from `models/llm/` after Whisper is unloaded

Sequential on purpose so both fit in 16 GB.

## Models (copied in, never fetched)

```
asr-llm/models/whisper/          # faster-whisper large-v3-turbo directory
asr-llm/models/llm/qwen2.5-7b-instruct-q4_k_m.gguf
```

7B Q4 is the default so CPU-32GB and 16GB GPU both work. Swap the GGUF path later if 14B fits after ASR unload.

## Glossary

`data/medical_ro_ru_en.json` ships with the repo — aligned RO/RU/EN terms. Whisper gets a short `hotwords` slice, the LLM gets the aligned table. See `data/SOURCES.md`.

## Run

```bash
cd asr-llm
pip install -e ".[asr,llm,dev]"
python -m asr_llm.cli ../data/Medpark_audio.m4a --skip-llm --out /tmp/transcript.json
python -m asr_llm.cli ../data/Medpark_audio.m4a --meeting-type medical --out /tmp/mom.json
```

`MOM_DEVICE=cpu` forces CPU. `MOM_DEVICE=cuda` requires a GPU.

## Tests

```bash
pytest   # no model weights, no network
```

The folder is `asr-llm` and the package is `asr_llm` on purpose: a folder named `asr_llm` shadows the installed package when you run from the repo root.
