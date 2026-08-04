"""Selects a `ReasoningBackend` implementation at runtime.

Returns `ClaudeBackend` when an Anthropic API key is configured (and the
backend isn't forced to "heuristic"), otherwise `HeuristicBackend`. This
is what makes the whole trigger -> investigate -> brief loop testable and
demoable with zero external API keys, while staying a drop-in real
integration once a key is added (`sentinel-spec` Global Constraints).

`ClaudeBackend`/`HeuristicBackend` are imported lazily, inside the
function body, so this module doesn't hard-fail at import time just
because `anthropic` client construction isn't wired up yet.
"""

from __future__ import annotations

from config import settings

from agents.reasoning_backend import ReasoningBackend


def get_reasoning_backend() -> ReasoningBackend:
    """Return the configured reasoning backend.

    - `reasoning_backend == "heuristic"` forces `HeuristicBackend`, even if
      an API key is set.
    - `reasoning_backend == "llm"` forces `ClaudeBackend`; raises
      `RuntimeError` if no API key is configured.
    - Otherwise (unset/auto-detect): `ClaudeBackend` if an API key is
      configured, else `HeuristicBackend`.
    """
    if settings.anthropic_api_key and settings.reasoning_backend != "heuristic":
        from agents.claude_backend import ClaudeBackend

        return ClaudeBackend()
    elif settings.reasoning_backend != "llm":
        from agents.heuristic_backend import HeuristicBackend

        return HeuristicBackend()
    else:
        raise RuntimeError(
            "reasoning_backend is forced to 'llm' but no ANTHROPIC_API_KEY is configured"
        )
