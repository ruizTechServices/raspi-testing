from __future__ import annotations

import pytest
import requests

from unified_server.providers import OllamaProvider


def test_ollama_provider_returns_clear_error_when_offline(monkeypatch):
    provider = OllamaProvider()

    def fake_post(*args, **kwargs):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(ValueError) as exc:
        provider.chat(messages=[{"role": "user", "content": "hello"}], model="mistral:latest")

    assert str(exc.value) == "Ollama is offline. Turn on the Ollama server to continue."


def test_ollama_provider_returns_clear_error_when_timed_out(monkeypatch):
    provider = OllamaProvider()

    def fake_post(*args, **kwargs):
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(ValueError) as exc:
        provider.chat(messages=[{"role": "user", "content": "hello"}], model="mistral:latest")

    assert str(exc.value) == "Ollama timed out while generating a reply. Check that the server is on and the model is responsive."
