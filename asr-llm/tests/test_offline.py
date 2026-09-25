import os
import socket

import numpy as np
import pytest

from asr_llm.batching import pack_batches
from asr_llm.glossary import asr_hotwords, llm_term_table
from asr_llm.offline import block_outbound
from asr_llm.vad import energy_vad


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


def test_pipeline_helpers_work_without_network(no_network):
    sr = 16_000
    silence = np.zeros(sr * 2, dtype=np.float32)
    t = np.arange(sr, dtype=np.float32) / sr
    tone = 0.2 * np.sin(2 * np.pi * 220 * t)
    audio = np.concatenate([silence, tone, silence])

    spans = energy_vad(audio, sample_rate=sr)
    batches = pack_batches(audio, spans, sample_rate=sr)

    assert batches
    assert asr_hotwords()
    assert "ro | ru | en" in llm_term_table()
