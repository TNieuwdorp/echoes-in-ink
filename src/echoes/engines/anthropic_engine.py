"""Cloud fallback: Claude via the official Anthropic SDK.

Off by default; only used when ``ANTHROPIC_API_KEY`` is set and the user passes
``--engine claude``. Thinking is adaptive by default on Claude Opus 5, so the
``thinking`` flag only lowers effort when False.
"""

from __future__ import annotations

from dataclasses import dataclass

import anthropic

from .base import Message, Reply, encode_image


@dataclass
class AnthropicEngine:
    name: str = "claude"
    model: str = "claude-opus-5"
    fallback_model: str = "claude-opus-4-8"
    image_max_side: int = 1568  # Claude downsizes beyond this anyway

    def __post_init__(self) -> None:
        self._client = anthropic.Anthropic()

    def _content(self, message: Message) -> list[dict]:
        out = []
        for part in message.parts:
            if part.kind == "text":
                out.append({"type": "text", "text": part.text})
            else:
                data, media = encode_image(part.path, self.image_max_side)
                out.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media, "data": data},
                    }
                )
        return out

    def chat(
        self,
        system: str,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        thinking: bool = False,
    ) -> Reply:
        payload = [{"role": m.role, "content": self._content(m)} for m in messages]
        # Sampling parameters are not accepted on Claude Opus 5; effort steers depth instead.
        response = self._client.beta.messages.create(
            model=self.model,
            max_tokens=max(max_tokens, 4096),
            system=system,
            messages=payload,
            output_config={"effort": "high" if thinking else "medium"},
            betas=["server-side-fallback-2026-06-01"],
            fallbacks=[{"model": self.fallback_model}],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError(f"Claude declined the request: {response.stop_details}")
        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        usage = response.usage
        return Reply(
            text=text,
            model=response.model,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )
