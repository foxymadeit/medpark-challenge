from mom.meeting_type import detect
from mom.schemas import Line


class Answer:
    def __init__(self, answer):
        self.answer, self.seen = answer, []

    def chat_json(self, system, user, schema, max_tokens=0, think=None):
        self.seen.append(user)
        if isinstance(self.answer, Exception):
            raise self.answer
        return {"meeting_type": self.answer}


def lines():
    return [Line(id=f"L{i:04d}", start=i * 60.0, end=i * 60.0 + 50, speaker="Speaker 1", text=f"line {i}") for i in range(6)]


def test_reads_only_the_first_three_minutes():
    llm = Answer("medical")
    assert detect(llm, lines()) == "medical"
    assert "line 3" in llm.seen[0] and "line 4" not in llm.seen[0]


def test_an_unknown_answer_or_a_failed_model_suggests_nothing():
    assert detect(Answer("social"), lines()) is None
    assert detect(Answer(TimeoutError("slow")), lines()) is None
