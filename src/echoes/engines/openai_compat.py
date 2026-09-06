"""Adapter for any OpenAI-compatible chat endpoint.

Used for the local vLLM server (default) and, optionally, for Google's Gemini
OpenAI-compatible endpoint. Thinking is toggled through vLLM's ``chat_template_kwargs``
for Qwen models; endpoints that do not understand that field get plain requests.
"""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from .base import Message, Reply, encode_image


@dataclass
class OpenAICompatEngine:
    name: str
    model: str
    base_url: str
    api_key: str = "EMPTY"
    supports_thinking_toggle: bool = True
    image_max_side: int = 2200
    timeout: float = 600.0

    def __post_init__(self) -> None:
        self._client = OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=self.timeout)

    def _content(self, message: Message) -> list[dict]:
        out = []
        for part in message.parts:
            if part.kind == "text":
                out.append({"type": "text", "text": part.text})
            else:
                data, media = encode_image(part.path, self.image_max_side)
                out.append(
                    {"type": "image_url", "image_url": {"url": f"data:{media};base64,{data}"}}
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
        payload = [{"role": "system", "content": system}]
        for m in messages:
            payload.append({"role": m.role, "content": self._content(m)})
        extra = {}
        if self.supports_thinking_toggle:
            extra["chat_template_kwargs"] = {"enable_thinking": thinking}
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=payload,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=extra or None,
        )
        choice = resp.choices[0]
        usage = resp.usage
        return Reply(
            text=choice.message.content or "",
            model=resp.model or self.model,
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
        )
