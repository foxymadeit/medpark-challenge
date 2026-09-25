# Backend

FastAPI service that receives an audio recording and forwards it to one downstream service.

## Requirements

- Python 3.14 or newer
- `uv` recommended for dependency management

## Setup

From this directory:

```powershell
uv sync
```

## Run the API

```powershell
uv run fastapi dev main.py
```

The API is available at `http://127.0.0.1:8000`.

Interactive API documentation is available at:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

## Upload audio

Send an audio file to `POST /audio`:

```powershell
curl.exe -X POST http://127.0.0.1:8000/audio -F "file=@recording.webm"
```

The response contains the filename, content type, and file size in bytes.

## Service flow

1. The API receives the user's uploaded audio file.
2. `InputService` reads the file and creates an `IngestedAudio` payload.
3. `InputService` sends the payload to one configured downstream consumer.
4. The API returns upload metadata to the caller.

The current `DownstreamService` in `main.py` is a placeholder. Replace its `consume()` method with the real transcription or audio-processing integration.

## Tests

Run the service tests with:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```
