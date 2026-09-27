"""The model's LaTeX body: parse it, allow only our commands, and hand the
same parsed blocks to both renderers.

The body may contain nothing but the commands in COMMANDS, each with exactly
its number of brace arguments, separated by whitespace. Inside an argument
only plain text is allowed, plus the escapes \\% \\& \\# \\_ \\$ and `~`, `--`.
Any other backslash, a stray brace or text outside a command is rejected.
That closes \\input, \\write18, \\catcode, ^^ tricks and every other way a
generated document could read files or run code.
"""

import re
from dataclasses import dataclass

# name -> argument names; the first argument of a fact command is its fact ID
COMMANDS = {
    "summary": ("id", "text"),
    "agendaitem": ("id", "title"),
    "topic": ("id", "title"),
    "presented": ("id", "who", "text"),
    "noted": ("id", "text"),
    "decision": ("id", "text", "vote"),
    "action": ("id", "owner", "deadline", "text"),
    "needsconfirmation": ("id", "text"),
    "nextmeeting": ("text",),
}
ENVIRONMENTS = {"agenda"}
_ESCAPES = {"%", "&", "#", "_", "$"}
_ID = re.compile(r"^[TNDACS]\d{1,3}$")


class BodyError(ValueError):
    """The body breaks the rules; the message says where and why."""


@dataclass(frozen=True)
class Block:
    kind: str          # a COMMANDS key, or "begin"/"end" for environments
    args: dict

    @property
    def fact_id(self):
        return self.args.get("id")


def parse(body: str) -> list:
    """Body text -> blocks. Raises BodyError on anything outside the rules."""
    if "^^" in body:
        raise BodyError("'^^' character escapes are not allowed")
    blocks, i, n = [], 0, len(body)
    while True:
        while i < n and body[i].isspace():
            i += 1
        if i >= n:
            break
        if body[i] != "\\":
            raise BodyError(f"text outside a command at {_where(body, i)}: {body[i:i + 30]!r}")
        m = re.match(r"\\([A-Za-z]+)", body[i:])
        if not m:
            raise BodyError(f"bad command at {_where(body, i)}")
        name, i = m.group(1), i + m.end()
        if name in ("begin", "end"):
            env, i = _arg(body, i)
            if env not in ENVIRONMENTS:
                raise BodyError(f"environment {env!r} is not allowed")
            blocks.append(Block(name, {"env": env}))
            continue
        if name not in COMMANDS:
            raise BodyError(f"command \\{name} is not allowed")
        values = []
        for _ in COMMANDS[name]:
            value, i = _arg(body, i)
            values.append(value)
        args = dict(zip(COMMANDS[name], values))
        if "id" in args and not _ID.match(args["id"]):
            raise BodyError(f"\\{name} has a bad fact ID {args['id']!r}")
        blocks.append(Block(name, args))
    _check_nesting(blocks)
    return blocks


def _arg(body: str, i: int):
    while i < len(body) and body[i] in " \t":
        i += 1
    if i >= len(body) or body[i] != "{":
        raise BodyError(f"missing argument at {_where(body, i)}")
    j = i + 1
    out = []
    while j < len(body):
        c = body[j]
        if c == "}":
            text = "".join(out)
            _check_text(text, body, i)
            return text, j + 1
        if c == "{":
            raise BodyError(f"unescaped '{{' inside an argument at {_where(body, j)}")
        if c == "\\":
            nxt = body[j + 1:j + 2]
            if nxt in _ESCAPES:
                out.append(c + nxt)
                j += 2
                continue
            raise BodyError(f"command inside an argument at {_where(body, j)}: {body[j:j + 20]!r}")
        out.append(c)
        j += 1
    raise BodyError(f"argument never closed, opened at {_where(body, i)}")


def _check_text(text: str, body: str, at: int) -> None:
    bad = re.search(r"(?<!\\)[%&#$_]", text)
    if bad:
        raise BodyError(f"unescaped {bad.group(0)!r} in an argument at {_where(body, at)}")


def _check_nesting(blocks) -> None:
    depth = 0
    for b in blocks:
        if b.kind == "begin":
            depth += 1
        elif b.kind == "end":
            depth -= 1
            if depth < 0:
                raise BodyError("\\end without \\begin")
        elif b.kind == "agendaitem" and depth == 0:
            raise BodyError("\\agendaitem outside the agenda environment")
    if depth:
        raise BodyError("an environment was never closed")


def _where(body: str, i: int) -> str:
    return f"line {body.count(chr(10), 0, i) + 1}"


def fact_ids(blocks) -> set:
    return {b.fact_id for b in blocks if b.fact_id}


def escape(text: str) -> str:
    """Plain text -> safe LaTeX argument text. Used for every value our own
    code puts in a document (names, titles, places), never trusted as is."""
    text = " ".join(str(text).split())   # a blank line inside an argument would end the paragraph
    text = text.replace("\\", " ").replace("{", "(").replace("}", ")")
    text = re.sub(r"([%&#$_])", r"\\\1", text)
    return text.replace("^", " ").replace("~", " ")


def unescape(text: str) -> str:
    """LaTeX argument text -> plain text, for the DOCX renderer and checks."""
    text = re.sub(r"\\([%&#_$])", r"\1", text)
    return text.replace("~", " ").replace("---", "—").replace("--", "–")


def serialise(blocks) -> str:
    """Blocks -> body text; the inverse of parse for well-formed input."""
    out = []
    for b in blocks:
        if b.kind in ("begin", "end"):
            out.append(f"\\{b.kind}{{{b.args['env']}}}")
        else:
            out.append(f"\\{b.kind}" + "".join("{" + b.args[k] + "}" for k in COMMANDS[b.kind]))
    return "\n".join(out) + "\n"
