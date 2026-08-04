import pytest

import agents.backend_factory as backend_factory


def test_uses_heuristic_when_no_api_key(monkeypatch):
    monkeypatch.setattr(backend_factory.settings, "anthropic_api_key", None)
    monkeypatch.setattr(backend_factory.settings, "reasoning_backend", None)
    backend = backend_factory.get_reasoning_backend()
    assert type(backend).__name__ == "HeuristicBackend"


def test_uses_claude_when_api_key_present(monkeypatch):
    monkeypatch.setattr(backend_factory.settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(backend_factory.settings, "reasoning_backend", None)
    backend = backend_factory.get_reasoning_backend()
    assert type(backend).__name__ == "ClaudeBackend"


def test_forced_heuristic_overrides_api_key(monkeypatch):
    monkeypatch.setattr(backend_factory.settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(backend_factory.settings, "reasoning_backend", "heuristic")
    backend = backend_factory.get_reasoning_backend()
    assert type(backend).__name__ == "HeuristicBackend"


def test_forced_llm_without_api_key_raises(monkeypatch):
    monkeypatch.setattr(backend_factory.settings, "anthropic_api_key", None)
    monkeypatch.setattr(backend_factory.settings, "reasoning_backend", "llm")
    with pytest.raises(RuntimeError):
        backend_factory.get_reasoning_backend()
