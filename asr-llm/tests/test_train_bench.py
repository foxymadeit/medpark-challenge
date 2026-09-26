import pytest

from asr_llm.clean import _fold
from asr_llm.score import edit_distance as runtime_edit_distance
from asr_train.common import GOLD, gold_text
from asr_train.metrics import edit_distance, fold, score
from asr_train.zeroshot import MATRIX, parse_args


@pytest.mark.parametrize("text", ["  Pacientul, cu INFARCT!  ", "Кровотечения нет… ok?", "și-a — ЭКГ, 12/80"])
def test_training_metrics_match_the_runtime_ruler(text):
    assert fold(text) == _fold(text)
    ref, hyp = list(fold(text)), list(fold(text[::-1]))
    assert edit_distance(ref, hyp) == runtime_edit_distance(ref, hyp)


def test_corpus_score():
    assert score(["a b c"], ["a b c"]) == {"cer": 0.0, "wer": 0.0, "n": 1}
    assert score(["a b", "c d"], ["a x", None])["wer"] == 0.75  # 1 sub + 2 del over 4 words


def test_gold_drops_note_lines():
    text = gold_text(GOLD)
    assert text and "#" not in text.split()[0]


def test_bench_args(tmp_path):
    args = parse_args(["--work", str(tmp_path), "--models", "parakeet", "--model-path", "parakeet=ft.nemo", "--sets", "gold,fleurs_ro"])
    assert args.models == ["parakeet"] and args.model_path == {"parakeet": "ft.nemo"} and args.sets == ["gold", "fleurs_ro"]
    assert parse_args(["--work", str(tmp_path)]).sets == list(MATRIX)
    assert parse_args(["--work", str(tmp_path), "--sets", "all"]).sets == list(MATRIX)
    for bad in (["--models", "gpt"], ["--model-path", "whisper=x"], ["--audio", str(tmp_path / "none.m4a")]):
        with pytest.raises(SystemExit):
            parse_args(["--work", str(tmp_path), *bad])


def test_recording_script_becomes_its_spoken_lines():
    from pathlib import Path

    from asr_train.common import ASR_ROOT, script_text

    text = script_text(ASR_ROOT / "data" / "recording_scripts" / "medical_round.md")
    assert text.startswith("Bun, colegi, începem.") and text.endswith("Ne vedem la 14.")
    assert "Подождите, подождите" in text and "Domnul Maxim" in text
    for markup in ("[B]", "(ro)", "⟂", "answers the phone", "Expected minutes", "|"):
        assert markup not in text
    assert gold_text(Path(ASR_ROOT / "data" / "recording_scripts" / "medical_round.md")) == text


def test_clip_only_run_downloads_nothing_and_keeps_the_cache(tmp_path, monkeypatch):
    import json
    import shutil

    from asr_train import zeroshot

    audio, ref = tmp_path / "rec.m4a", tmp_path / "ref.txt"
    audio.write_bytes(b"x")
    ref.write_text("# note\nBună ziua\n")
    work = tmp_path / "work"
    work.mkdir()
    (work / "sets.json").write_text(json.dumps({"fleurs_ro": [{"audio": "a.wav", "text": "t"}]}))

    monkeypatch.setattr(zeroshot, "ffmpeg_16k", lambda src, dest, *extra: shutil.copy(src, dest) and dest)
    monkeypatch.setattr(zeroshot, "build_sets", lambda *a: pytest.fail("clip-only run must not build public sets"))
    seen = {}
    monkeypatch.setattr(zeroshot, "run_nemo", lambda bench, hub, kind, sets, path, device: seen.update(sets))

    zeroshot.main(["--work", str(work), "--models", "parakeet", "--device", "cpu", "--clip", f"syn={audio},{ref}"])
    assert list(seen) == ["clip_syn"] and seen["clip_syn"][0]["text"] == "Bună ziua"
    assert json.loads((work / "sets.json").read_text()) == {"fleurs_ro": [{"audio": "a.wav", "text": "t"}]}  # cache untouched
    assert list(json.loads((work / "run_sets.json").read_text())) == ["clip_syn"]


def test_clip_args_and_scoring(tmp_path):
    from asr_train.zeroshot import is_long, matrix, score_items

    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"")
    args = parse_args(["--work", str(tmp_path), "--clip", f"x={audio}", "--sets", "gold"])
    assert args.clip == {"x": (audio, None)} and args.sets == ["gold"]
    for bad in ("x", f"={audio}", f"x={tmp_path / 'none.m4a'}", f"x={audio},{tmp_path / 'none.txt'}"):
        with pytest.raises(SystemExit):
            parse_args(["--work", str(tmp_path), "--clip", bad])
    assert is_long("gold") and is_long("clip_x") and not is_long("fleurs_ro")
    assert matrix("clip_x") == "ro" and matrix("fleurs_ru") == "ru"
    assert score_items([{"audio": "a", "text": None}], ["hyp"]) == {"n": 1, "scored": False}
    assert score_items([{"audio": "a", "text": "a b"}], ["a b"])["wer"] == 0.0
