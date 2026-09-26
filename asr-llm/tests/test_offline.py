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
