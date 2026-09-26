import pytest

from mom.latexcheck import BodyError, escape, fact_ids, parse, serialise, unescape

GOOD = r"""
\begin{agenda}
\agendaitem{T1}{Contractul RMN}
\end{agenda}
\topic{T1}{Contractul RMN}
\presented{N1}{dl Victor Munteanu}{Dl Victor Munteanu a comunicat că reducerea este de 10\%.}
\decision{D1}{Se aprobă reînnoirea.}{pro 4, contra 0}
\action{A1}{dl Victor Munteanu}{30.09.2026}{Verifică condițiile.}
\needsconfirmation{C1}{Cine trimite documentele.}
\nextmeeting{03.10.2026, ora 14:00.}
"""


def test_a_well_formed_body_parses_into_blocks_with_fact_ids():
    blocks = parse(GOOD)
    assert [b.kind for b in blocks][:3] == ["begin", "agendaitem", "end"]
    assert fact_ids(blocks) == {"T1", "N1", "D1", "A1", "C1"}
    action = next(b for b in blocks if b.kind == "action")
    assert action.args == {"id": "A1", "owner": "dl Victor Munteanu", "deadline": "30.09.2026", "text": "Verifică condițiile."}
    assert parse(serialise(blocks)) == blocks


@pytest.mark.parametrize("attack", [
    r"\input{/etc/passwd}",
    r"\immediate\write18{rm -rf /}",
    r"\noted{N1}{text \input{/etc/passwd}}",
    r"\noted{N1}{\catcode`\@=11}",
    r"\noted{N1}{^^5cinput}",
    r"\openout\f=x.tex",
    r"\noted{N1}{a {nested} group}",
    r"\noted{N1}{never closed",
    r"\decision{D1}{only two args}",
    r"free text between commands \noted{N1}{x}",
    r"\noted{N1}{50% off}",
    r"\noted{X9}{bad id}",
    r"\begin{document}",
    r"\agendaitem{T1}{outside the agenda}",
])
def test_everything_outside_the_vocabulary_is_rejected(attack):
    with pytest.raises(BodyError):
        parse(attack)


def test_escape_makes_any_text_safe_and_unescape_reverses_it():
    nasty = r"Dr. X {\input{/etc/passwd}} 50% & #1 $5 a_b ^^5c ~"
    safe = escape(nasty)
    parse(r"\noted{N1}{" + safe + "}")  # would raise if anything slipped through
    assert "\\input" not in safe
    assert unescape(r"10\% \& a\_b") == "10% & a_b"
