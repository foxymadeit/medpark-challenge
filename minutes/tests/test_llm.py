import pytest

from mom.llm import LocalLLM, check_local


@pytest.mark.parametrize("url", ["http://127.0.0.1:11434", "http://localhost:8080", "http://[::1]:8080"])
def test_loopback_addresses_are_accepted(url):
    assert check_local(url)


@pytest.mark.parametrize("url", ["http://10.0.0.5:11434", "https://api.openai.com", "http://192.168.1.2:8080", "http://evil.localhost.com"])
def test_anything_off_this_machine_is_refused(url):
    with pytest.raises(ValueError):
        LocalLLM(url=url)


def test_proxy_settings_are_ignored():
    # HTTP_PROXY must never carry a transcript off the machine: the opener has
    # no proxy handler at all, so environment proxies are never consulted
    from mom import llm
    assert not any(getattr(h, "proxies", None) for h in llm._OPENER.handlers)
    assert not any(type(h).__name__ == "HTTPRedirectHandler" for h in llm._OPENER.handlers)
