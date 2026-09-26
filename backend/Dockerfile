# Liminal backend. The pipeline tools (asr_llm, diarizer, mom) and their models
# are installed into this image on the reference server; the stage commands
# are set with LIMINAL_ASR_CMD, LIMINAL_DIARIZE_CMD and LIMINAL_MINUTES_CMD.
FROM python:3.14-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home liminal
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir "fastapi[standard]>=0.141.1" "python-dotenv>=1.0"
COPY . .
USER liminal
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
