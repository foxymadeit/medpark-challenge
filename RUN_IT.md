# Run Liminal on your machine

It should work, but we've never run the whole product on an Apple Silicon Mac. Every part is tested (497 tests), and the full pipeline has run end to end, but only on Linux with an NVIDIA T4 (Kaggle). An M4 runs it differently:

- Transcription runs Whisper large-v3 on the Apple GPU through MLX (`MOM_ASR_ENGINE=mlx`, the `mac` profile the app picks by itself on Apple Silicon). faster-whisper, used on Linux, has no Apple-GPU backend.
- The minutes model uses the Apple GPU through Ollama. gpt-oss:20b (13 GB) fits comfortably in 24 GB.
- Expect it to be slower than the T4, so test with the 11.7-minute Medpark sample first, not an hour.

## Once, with internet (~40 min, mostly downloads)

```bash
brew install python@3.12 uv node ffmpeg git
brew install --cask docker ollama mactex-no-gui     # open Docker Desktop and Ollama once afterwards
# MacTeX is a 7 GB download. If the mirror drops it, run the same command again (it resumes); if brew then
# says installed but `xelatex` is missing, install the cached package:
#   sudo installer -pkg ~/Library/Caches/Homebrew/downloads/*mactex*.pkg -target /
git clone -b test https://github.com/foxymadeit/medpark-challenge ~/liminal && cd ~/liminal
python3.12 -m venv .tools && source .tools/bin/activate
pip install -e diarization -e minutes -e 'asr-llm[asr,mlx]'
python asr-llm/scripts/fetch_whisper.py mlx large-v3      # mlx: the Apple-GPU weights; large-v3: the CPU engine
ollama pull gpt-oss:20b
(cd frontend && npm ci && npm run build)
(cd backend && uv sync && bash n8n/setup.sh)       # starts Mailpit and n8n, writes the secrets
```

## Every run (Wi-Fi can be off)

```bash
cd ~/liminal/backend
T=~/liminal/.tools/bin
export LIMINAL_PROFILE=mac                 # Whisper large-v3 on the GPU (MLX) and gpt-oss:20b; the default on Apple Silicon with 20 GB+
export LIMINAL_FRONTEND_DIST=../frontend/dist
export LIMINAL_N8N_WEBHOOK=http://127.0.0.1:5678/webhook/liminal-minutes
export LIMINAL_ASR_CMD="$T/python -m asr_llm.cli {audio} --skip-llm --out {work}/asr.json"
export LIMINAL_DIARIZE_CMD="$T/diarizer file {audio} --out {work}/diarization --plain"
export LIMINAL_MINUTES_CMD="$T/mom report {work}/transcript.json --session {session} --type {type} --date {date} --start {start} --out {work}/minutes"
export LIMINAL_RENDER_CMD="$T/mom render {render} --type {type}"
uv run uvicorn main:app --host 127.0.0.1 --port 8001   # 8000 is taken by the Docker gateway setup.sh starts
```

Then:
1. Open http://127.0.0.1:8001, pick Medical, and upload `~/liminal/asr-llm/data/Medpark_audio.m4a`.
2. Watch the email arrive in Mailpit at http://127.0.0.1:8025.

Why the pipeline tools are set with full paths: the backend needs Python 3.14, and the ASR libraries are safest on 3.12. Without these settings, the backend would call its own Python, which lacks the tools.

Likely snags:
- A missing LaTeX package. The full `mactex-no-gui` avoids that.
- Docker Desktop not running when `setup.sh` starts.
- The clone path containing a space. Keep it at `~/liminal`.

If a stage fails, its log is under `backend/data/…/logs/`.
