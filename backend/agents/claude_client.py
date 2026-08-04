"""Lazy singleton construction of the Anthropic SDK client.

Kept in its own module (rather than constructed inline in
`ClaudeBackend.__init__`) so `agents.claude_backend` can be imported
freely without requiring `settings.anthropic_api_key` to be configured
— only calling `get_anthropic_client()` (the default when
`ClaudeBackend` is built without an injected `client`) does that, and
only the first call actually constructs the `anthropic.Anthropic`
instance. Tests inject a fake client directly into `ClaudeBackend` and
never touch this module, so they need no real API key or network
access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from config import settings

if TYPE_CHECKING:
    import anthropic

_client: "anthropic.Anthropic | None" = None


def get_anthropic_client() -> "anthropic.Anthropic":
    """Return a process-wide `anthropic.Anthropic` client, constructing it once."""
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client
