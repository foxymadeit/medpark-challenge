"""The local language model, reached only on this machine.

Two local servers are supported: Ollama (default, http://127.0.0.1:11434)
and llama.cpp's llama-server (OpenAI-style API). Any address that is not
loopback is refused, so a wrong setting cannot send a transcript anywhere.
Output is constrained to a JSON schema and decoded at temperature 0.
"""

import ipaddress
import json
import os
import time
import urllib.request
from urllib.parse import urlparse

DEFAULT_URL = os.environ.get("MOM_LLM_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("MOM_LLM_MODEL", "gemma3:12b")
TIMEOUT = float(os.environ.get("MOM_LLM_TIMEOUT", "900"))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None   # a redirect could point anywhere; the answer must come from the loopback server


# No proxy: urllib otherwise honours HTTP_PROXY and could route the transcript
# through a corporate proxy even though the address is 127.0.0.1.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)


def check_local(url: str) -> str:
    host = urlparse(url).hostname or ""
    try:
        local = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        local = False
    if not local:
        raise ValueError(f"the language model must run on this machine; {host!r} is not a loopback address")
    return url.rstrip("/")


class LocalLLM:
    def __init__(self, model: str = DEFAULT_MODEL, url: str = DEFAULT_URL, backend: str = "", ctx: int = 16384):
        self.url = check_local(url)
        self.model = model
        self.backend = backend or ("ollama" if url.rstrip("/").endswith(":11434") else "openai")
        self.ctx = ctx
        self.stats = {"calls": 0, "prompt_tokens": 0, "output_tokens": 0, "seconds": 0.0}
        self.cpu_only = False   # bake-off: measure CPU-only speed on a GPU machine

    def _post(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with _OPENER.open(req, timeout=TIMEOUT) as r:   # noqa: S310 (loopback only, checked above)
            return json.loads(r.read())

    def chat(self, system: str, user: str, schema: dict = None, max_tokens: int = 2048, think=None) -> str:
        t0 = time.perf_counter()
        if self.backend == "ollama":
            body = {"model": self.model, "stream": False, "keep_alive": "10m",
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "options": {"temperature": 0, "num_predict": max_tokens, "num_ctx": self.ctx, "seed": 7}}
            if schema:
                body["format"] = schema
            if think is not None:
                body["think"] = think
            if self.cpu_only:
                body["options"]["num_gpu"] = 0
            out = self._post("/api/chat", body)
            text = out["message"]["content"]
            self.stats["prompt_tokens"] += out.get("prompt_eval_count", 0)
            self.stats["output_tokens"] += out.get("eval_count", 0)
        else:
            body = {"model": self.model, "temperature": 0, "max_tokens": max_tokens, "seed": 7,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
            if schema:
                body["response_format"] = {"type": "json_schema", "json_schema": {"name": "out", "schema": schema}}
            out = self._post("/v1/chat/completions", body)
            text = out["choices"][0]["message"]["content"]
            usage = out.get("usage") or {}
            self.stats["prompt_tokens"] += usage.get("prompt_tokens", 0)
            self.stats["output_tokens"] += usage.get("completion_tokens", 0)
        self.stats["calls"] += 1
        self.stats["seconds"] += time.perf_counter() - t0
        return text

    def chat_json(self, system: str, user: str, schema: dict, max_tokens: int = 2048, think=None) -> dict:
        text = self.chat(system, user, schema, max_tokens, think)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start:end + 1])
            raise
