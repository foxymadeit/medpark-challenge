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
    for bad in (["--models", "gpt"], ["--model-path", "whisper=x"], ["--audio", str(tmp_path / "none.m4a")]):
        with pytest.raises(SystemExit):
            parse_args(["--work", str(tmp_path), *bad])
