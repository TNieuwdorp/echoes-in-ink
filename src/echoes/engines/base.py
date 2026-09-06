"""Engine protocol shared by local (vLLM) and cloud adapters.

An engine takes a system prompt and a list of chat messages whose content is a list of
``Part`` (text or image path) and returns the assistant's text. Multi-turn messages are
used for few-shot examples: image → gold transcription pairs precede the target page.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from PIL import Image


@dataclass(frozen=True)
class Part:
    kind: Literal["text", "image"]
    text: str = ""
    path: Path | None = None

    @staticmethod
    def of_text(text: str) -> Part:
        return Part("text", text=text)

    @staticmethod
    def of_image(path: Path) -> Part:
        return Part("image", path=Path(path))


@dataclass
class Message:
    role: Literal["user", "assistant"]
    parts: list[Part]


@dataclass
class Reply:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class Engine(Protocol):
    name: str
    model: str

    def chat(
        self,
        system: str,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        thinking: bool = False,
    ) -> Reply: ...


def encode_image(path: Path, max_side: int = 2200, quality: int = 90) -> tuple[str, str]:
    """Return (base64 JPEG, media type), downscaling so the long side is <= max_side."""
    with Image.open(path) as img:
        img = img.convert("RGB") if img.mode not in ("RGB", "L") else img
        w, h = img.size
        scale = max_side / max(w, h)
        if scale < 1:
            img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
    return base64.standard_b64encode(buf.getvalue()).decode("ascii"), "image/jpeg"
