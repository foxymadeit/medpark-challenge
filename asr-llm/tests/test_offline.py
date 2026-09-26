import os
import socket

import pytest

from asr_llm.batching import pack_batches
from asr_llm.offline import block_outbound
from asr_llm.retrieve import llm_glossary_for
from asr_llm.vad import speech_spans


@pytest.fixture
def no_network():
    restore = block_outbound()
    yield
    restore()


def test_hub_lookups_are_disabled_on_import():
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"


def test_outbound_connection_is_refused(no_network):
    with pytest.raises(OSError, match="network disabled"):
        socket.create_connection(("huggingface.co", 443), timeout=1)


def test_pipeline_helpers_work_without_network(no_network, meeting_audio):
    spans = speech_spans(meeting_audio)
    batches = pack_batches(meeting_audio, spans)

    assert batches
    assert "ro | ru | en" in llm_glossary_for("pacient cu hipertensiune")


def test_ollama_backend_is_loopback_only(monkeypatch):
    from asr_llm.config import settings
    from asr_llm.llm import OllamaLlm, make_llm

    monkeypatch.setattr(settings, "ollama_url", "http://10.0.0.5:11434")
    with pytest.raises(ValueError, match="must be local"):
        make_llm("ollama:qwen3.5:9b")

    monkeypatch.setattr(settings, "ollama_url", "http://127.0.0.1:11434")
    llm = make_llm("ollama:qwen3.5:9b")
    assert isinstance(llm, OllamaLlm)
    sent = {}
    monkeypatch.setattr(llm, "_post", lambda path, body: sent.update(body) or {"message": {"content": '{"ok": 1}'}})
    assert llm.chat_json("sys", "user", max_tokens=10) == {"ok": 1}
    assert sent["model"] == "qwen3.5:9b" and sent["format"] == "json"
