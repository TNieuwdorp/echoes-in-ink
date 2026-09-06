"""Engine registry. Everything is local unless a cloud engine is asked for explicitly."""

from __future__ import annotations

import os
import shutil

from .base import Engine, Message, Part, Reply

LOCAL_BASE_URL = os.environ.get("ECHOES_LOCAL_BASE_URL", "http://localhost:8000/v1")
LOCAL_MODEL = os.environ.get("ECHOES_LOCAL_MODEL", "qwen38")  # the --served-model-name of a preset
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")


def get_engine(name: str = "local", model: str | None = None) -> Engine:
    """``local`` (vLLM), ``gemini`` (best-value cloud, needs a key) or ``claude`` (top performer).

    ``claude`` picks the SDK when ``ANTHROPIC_API_KEY`` is set and otherwise the Claude Code CLI
    on the user's subscription login; ``claude-api`` and ``claude-cli`` force one of the two.
    """
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
    if name in ("claude", "claude-api", "claude-cli"):
        want = model or "claude-opus-5"
        has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        has_cli = shutil.which("claude") is not None
        if name == "claude-api" or (name == "claude" and has_key):
            if not has_key:
                raise RuntimeError("ANTHROPIC_API_KEY is not set; use --engine claude-cli instead")
            from .anthropic_engine import AnthropicEngine

            return AnthropicEngine(model=want)
        if not has_cli:
            raise RuntimeError(
                "neither ANTHROPIC_API_KEY nor a `claude` CLI on PATH; "
                "install Claude Code and run `claude auth login`"
            )
        from .claude_cli import ClaudeCliEngine

        return ClaudeCliEngine(model=want)
    raise ValueError(
        f"unknown engine {name!r}; choose local, gemini, claude, claude-cli or claude-api"
    )


__all__ = ["Engine", "Message", "Part", "Reply", "get_engine"]
