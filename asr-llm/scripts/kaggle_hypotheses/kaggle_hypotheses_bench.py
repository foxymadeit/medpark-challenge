"""Kaggle T4 bench: every transcriber on the same Medpark utterances.

Dev-time only (Internet ON for installs and weights). Every model is pinned to
one T4 so timings match the 16 GB reference box. Writes /kaggle/working/out/*.json,
one file per system, segments aligned by index with the Whisper run.

Push from the repo root:
    kaggle kernels push -p asr-llm/scripts/kaggle_hypotheses   (this folder)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

WORK = Path("/kaggle/working")
OUT = WORK / "out"
REPO = WORK / "repo"
OUT.mkdir(parents=True, exist_ok=True)

MIXED_PROMPT = (
    "Transcribe this audio from a hospital meeting in Moldova exactly as spoken. "
    "Speakers mix Romanian, Russian and English, sometimes inside one sentence. "
    "Write Romanian words in Latin script with Romanian diacritics, Russian words in Cyrillic, "
    "English words in English. Do not translate anything. Output only the transcript."
)
PLAIN_PROMPT = "Transcribe the following speech segment in its original language."


def sh(cmd: str) -> None:
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


def save(name: str, payload: dict) -> None:
    (OUT / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"saved {name}", flush=True)


def setup() -> Path:
    sh(f"git clone -q --depth 1 -b samoilov-asr-llm https://github.com/foxymadeit/medpark-challenge {REPO}")
    sh(f"pip install -q -e {REPO}/asr-llm[asr] huggingface_hub soundfile")
    sh("pip install -q -U transformers accelerate bitsandbytes")  # Gemma 4 needs a recent transformers
    sh(f"cd {REPO}/asr-llm && python scripts/fetch_whisper.py large-v3 turbo")
    return next(Path("/kaggle/input").rglob("*.m4a"))


def whisper_child(audio_path: Path, model_dir: str, name: str) -> None:
    """Runs in its own process: importing asr_llm switches Hugging Face to offline
    mode, which is right for the product and wrong for the Gemma downloads below."""
    sys.path.insert(0, str(REPO / "asr-llm"))
    os.environ.update(MOM_DEVICE="cuda", MOM_ASR_COMPUTE_TYPE="int8_float16", MOM_ASR_MODEL_DIR=model_dir)
    from asr_llm.pipeline import transcribe_audio

    t0 = time.perf_counter()
    transcript, timings = transcribe_audio(audio_path)
    save(name, {"wall_s": time.perf_counter() - t0, "timings": timings, "transcript": transcript.model_dump()})
    clips = [(s, e, str(p)) for s, e, p in utterances(audio_path)]
    (WORK / "clips.json").write_text(json.dumps(clips))


def whisper(audio_path: Path, model_dir: str, name: str) -> None:
    script = globals().get("__file__") or sys.argv[0]
    sh(f"{sys.executable} {script} whisper {audio_path} {model_dir} {name}")


def utterances(audio_path: Path):
    """Same cut as the pipeline, written to wav for the models that want files."""
    import soundfile as sf

    from asr_llm.audio import decode_audio
    from asr_llm.batching import pack_batches
    from asr_llm.vad import speech_spans

    audio = decode_audio(audio_path)
    clips = []
    for b in pack_batches(audio, speech_spans(audio)):
        path = WORK / "clips" / f"{b.index:04d}.wav"
        path.parent.mkdir(exist_ok=True)
        sf.write(path, b.samples, 16_000)
        clips.append((b.start, b.end, path))
    return clips


def gemma(model_id: str, clips, prompts: dict[str, str], four_bit: bool) -> None:
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor, BitsAndBytesConfig

    kwargs = {"device_map": {"": 0}, "torch_dtype": torch.float16}
    if four_bit:
        kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
    t0 = time.perf_counter()
    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForImageTextToText.from_pretrained(model_id, **kwargs)
    load_s = time.perf_counter() - t0
    tag = model_id.split("/")[-1].lower()
    for prompt_name, prompt in prompts.items():
        rows, t0 = [], time.perf_counter()
        for start, end, path in clips:
            messages = [{"role": "user", "content": [{"type": "audio", "audio": str(path)}, {"type": "text", "text": prompt}]}]
            inputs = processor.apply_chat_template(
                messages, add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors="pt"
            ).to(model.device)
            with torch.inference_mode():
                out = model.generate(**inputs, max_new_tokens=256, do_sample=False)
            raw = processor.decode(out[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True)
            text = re.sub(r"<[^>]*think[^>]*>.*?</[^>]*think[^>]*>", "", raw, flags=re.S).strip()
            rows.append({"start": start, "end": end, "text": text})
        save(f"{tag}_{prompt_name}", {"model": model_id, "load_s": load_s, "asr_s": time.perf_counter() - t0, "segments": rows})
    del model
    torch.cuda.empty_cache()


def omni(clips) -> None:
    sh("pip install -q omnilingual-asr torch==2.8.0 torchaudio==2.8.0")  # fairseq2 pins torch 2.8
    from omnilingual_asr.models.inference.pipeline import ASRInferencePipeline

    t0 = time.perf_counter()
    pipe = ASRInferencePipeline(model_card="omniASR_CTC_1B")
    load_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    texts = pipe.transcribe([str(p) for _, _, p in clips], batch_size=4)
    rows = [{"start": s, "end": e, "text": t} for (s, e, _), t in zip(clips, texts)]
    save("omniasr_ctc_1b", {"load_s": load_s, "asr_s": time.perf_counter() - t0, "segments": rows})


def run(name: str, fn, *args) -> None:
    try:
        fn(*args)
    except Exception:
        (OUT / f"{name}.error.txt").write_text(traceback.format_exc())
        traceback.print_exc()


if __name__ == "__main__":
    if sys.argv[1:2] == ["whisper"]:
        whisper_child(Path(sys.argv[2]), sys.argv[3], sys.argv[4])
        sys.exit(0)
    audio_path = setup()
    models = REPO / "asr-llm/models"
    run("whisper_dual", whisper, audio_path, str(models / "whisper"), "whisper_dual")
    run("whisper_turbo_dual", whisper, audio_path, str(models / "whisper-turbo"), "whisper_turbo_dual")
    clips = [(s, e, Path(p)) for s, e, p in json.loads((WORK / "clips.json").read_text())]
    prompts = {"plain": PLAIN_PROMPT, "mixed": MIXED_PROMPT}
    run("gemma4_e4b", gemma, "google/gemma-4-E4B-it", clips, prompts, False)
    run("gemma4_12b", gemma, "google/gemma-4-12B-it", clips, prompts, True)
    run("omniasr", omni, clips)  # last: its install may change torch
