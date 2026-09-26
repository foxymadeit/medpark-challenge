from asr_llm.fuse import fuse_debate, fuse_single, grounded, is_unclear
from asr_llm.schemas import Hypothesis, SpeechSegment


def seg(i, ro, ru, s_ro, s_ru):
    return SpeechSegment(
        start=i,
        end=i + 1,
        text=ro if s_ro >= s_ru else ru,
        language="ro" if s_ro >= s_ru else "ru",
        hypotheses=[Hypothesis(language="ro", text=ro, score=s_ro), Hypothesis(language="ru", text=ru, score=s_ru)],
    )


MIXED = seg(0, "Pacientul primește dozile de nor", "Пациент получает дозы нора", -0.50, -0.55)
CLEAR = seg(1, "Facem ecografie mâine", "Делаем эхо завтра", -0.20, -0.90)


class FakeLlm:
    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def chat_json(self, system, user, max_tokens):
        self.calls.append(user)
        ids = [int(line.split("=")[1].split()[0]) for line in user.splitlines() if line.startswith("id=")]
        return {"utterances": [{"id": i, "text": self.answers[i], "languages": ["ro", "ru"]} for i in ids if i in self.answers]}

    def close(self):
        pass


def test_unclear_means_close_scores_or_poor_best():
    assert is_unclear(MIXED, margin=0.15, floor=-0.8)
    assert not is_unclear(CLEAR, margin=0.15, floor=-0.8)
    assert is_unclear(seg(2, "a", "b", -0.95, -1.5), margin=0.15, floor=-0.8)


def test_grounding_rejects_invented_words():
    assert grounded("Pacientul получает dozile de nor", MIXED, 0.85)
    assert not grounded("Pacientul primește noradrenalină intravenos", MIXED, 0.85)


def test_single_only_touches_unclear_and_keeps_guard():
    llm = FakeLlm({0: "Pacientul получает dozile de nor", 1: "invented text"})
    out = fuse_single(llm, [MIXED, CLEAR])
    assert out[0].text == "Pacientul получает dozile de nor"
    assert out[0].language == "ro+ru"
    assert out[1] == CLEAR
    assert all("id=1" not in call for call in llm.calls)


def test_single_falls_back_when_llm_invents():
    out = fuse_single(FakeLlm({0: "Pacientul primește noradrenalină intravenos"}), [MIXED])
    assert out[0] == MIXED


def test_debate_majority_wins_and_second_round_sees_others():
    good = "Pacientul получает dozile de nor"
    models = [FakeLlm({0: good, 1: "Facem ecografie mâine"}) for _ in range(2)]
    models.append(FakeLlm({0: "Pacientul primește dozile de nor", 1: "Facem ecografie mâine"}))
    out = fuse_debate([lambda m=m: m for m in models], [MIXED, CLEAR], rounds=2, window=1)
    assert out[0].text == good
    assert out[1].text == "Facem ecografie mâine"
    assert any("Other reviewers" in call for call in models[0].calls)
    assert len(models[0].calls) == 4  # 2 utterances x 2 rounds: every sentence, every round


def test_wholesale_swap_to_worse_scored_hypothesis_is_rejected():
    # ro fits the audio better; the LLM prefers the fluent Russian translation.
    s = seg(3, "și dreapta și stânga", "и правая и левая", -0.35, -0.66)
    s_unclear = seg(4, "și dreapta și stânga", "и правая и левая", -0.50, -0.58)
    llm = FakeLlm({1: "и правая и левая"})
    assert fuse_single(llm, [s, s_unclear])[1] == s_unclear
    assert llm.calls, "the unclear utterance must reach the LLM"
    mixed = FakeLlm({1: "și dreapta и левая"})
    assert fuse_single(mixed, [s, s_unclear])[1].text == "și dreapta и левая"
