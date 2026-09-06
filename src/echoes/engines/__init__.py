"""Engine registry. Everything is local unless an API key is configured and asked for."""

from __future__ import annotations

import os

from .base import Engine, Message, Part, Reply

LOCAL_BASE_URL = os.environ.get("ECHOES_LOCAL_BASE_URL", "http://localhost:8000/v1")
LOCAL_MODEL = os.environ.get("ECHOES_LOCAL_MODEL", "Qwen/Qwen3.8-27B")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")


def get_engine(name: str = "local", model: str | None = None) -> Engine:
    """``local`` (vLLM), ``gemini`` (best-value cloud) or ``claude`` (top-performer cloud)."""
    if name == "local":
        from .openai_compat import OpenAICompatEngine

        return OpenAICompatEngine(name="local", model=model or LOCAL_MODEL, base_url=LOCAL_BASE_URL)
    if name == "gemini":
        from .openai_compat import OpenAICompatEngine

        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set; cloud engines are opt-in")
        return OpenAICompatEngine(
            name="gemini",
            model=model or GEMINI_MODEL,
            base_url=GEMINI_BASE_URL,
            api_key=key,
            supports_thinking_toggle=False,
        )
    if name == "claude":
        from .anthropic_engine import AnthropicEngine

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set; cloud engines are opt-in")
        return AnthropicEngine(model=model or "claude-opus-5")
    raise ValueError(f"unknown engine {name!r}; choose local, gemini or claude")


__all__ = ["Engine", "Message", "Part", "Reply", "get_engine"]
