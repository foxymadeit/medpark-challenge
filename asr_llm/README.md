# Medpark ASR + local LLM

Your slice of Secure MOM: **audio → VAD batches → local Whisper → local LLM minutes**.

Diarization lives on `Coflazo-Branch` (`diarization/`). This package only consumes `session.json` if you pass `--diarization`.

## Why FastAPI

Keep it. The rest of the stack is Python (diarizer, numpy, Whisper). FastAPI is the thinnest way to expose `/minutes` to the web app and to n8n later. Do not add Celery yet.

## Pipeline

```
audio (m4a/wav)
  → ffmpeg 16 kHz mono
  → energy VAD (silence skip)
  → packs ≤30 s batches (language-agnostic)
  → one multilingual Whisper (MLX on M4, faster-whisper on CUDA/CPU)
  → optional speaker labels by time overlap with diarization turns
  → Ollama Qwen 2.5 (JSON minutes)
```

No language router. No three ASR models.

## Setup (M4 Pro)

```bash
cd asr_llm
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[mlx,dev]"
brew install ffmpeg
ollama pull qwen2.5:14b
```

First Whisper run downloads weights. After that, disconnect the network.

## Run

```bash
# ASR only, no LLM (good first smoke test)
python -m asr_llm.cli ../data/Medpark_audio.m4a --skip-llm --out /tmp/transcript.json

# Full minutes
python -m asr_llm.cli ../data/Medpark_audio.m4a --meeting-type medical --out /tmp/mom.json

# API
uvicorn asr_llm.api:app --host 127.0.0.1 --port 8000
```

```bash
curl -F audio=@../data/Medpark_audio.m4a -F meeting_type=medical http://127.0.0.1:8000/minutes
```

## Tests (no models)

```bash
pytest
```

## Env

| Variable | Default | Meaning |
|---|---|---|
| `MOM_ASR_BACKEND` | `auto` | `mlx` on Apple Silicon, else `faster-whisper` |
| `MOM_ASR_MODEL` | `large-v3-turbo` | start turbo, compare `large-v3` on the Medpark file |
| `MOM_LLM_MODEL` | `qwen2.5:14b` | Ollama tag |
| `MOM_OLLAMA_HOST` | `http://127.0.0.1:11434` | local only |

Ollama on localhost is still on-prem. Gmail/OpenAI/cloud Whisper is not.

## Next on this branch

1. Measure ASR on `data/Medpark_audio.m4a` (turbo vs large-v3).
2. Swap energy VAD for Silero if quiet speakers are dropped.
3. Tighten the LLM JSON prompt on a real transcript.
4. Add async jobs in FastAPI only after the CLI path is correct.
