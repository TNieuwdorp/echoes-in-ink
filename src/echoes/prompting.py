"""Prompt loading, versioning and few-shot assembly."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import polars as pl

from . import schema
from .engines import Message, Part

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load_prompt(name: str) -> tuple[str, str]:
    """Return (template, version) where version is a short hash of the file content."""
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return text, hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def load_names(path: Path | None = None) -> list[str]:
    path = path or schema.data_path("names.txt")
    if not path.exists():
        return []
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]


def render(template: str, **fields: str) -> str:
    for key, value in fields.items():
        template = template.replace("{" + key + "}", value)
    return template


def holdout_stems(gold_dir: Path) -> set[str]:
    f = gold_dir / "holdout.txt"
    if not f.exists():
        return set()
    return {
        ln.strip() for ln in f.read_text().splitlines() if ln.strip() and not ln.startswith("#")
    }


def gold_to_json(text: str) -> str:
    """Turn a gold .txt into the JSON the model is asked to produce (for few-shot answers)."""
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    return json.dumps(
        {"lines": [{"n": i + 1, "text": ln, "confidence": "high"} for i, ln in enumerate(lines)]},
        ensure_ascii=False,
    )


def few_shot_examples(
    pages: pl.DataFrame,
    gold: pl.DataFrame,
    processed_dir: Path,
    exclude_page_id: str,
    gold_dir: Path,
    k: int = 2,
) -> list[Message]:
    """Build alternating user(image)/assistant(json) turns from gold pages."""
    if k <= 0 or gold.is_empty():
        return []
    holdout = holdout_stems(gold_dir)
    stems = {
        pid: Path(fn).stem for pid, fn in zip(pages["page_id"], pages["filename"], strict=True)
    }
    messages: list[Message] = []
    for row in gold.iter_rows(named=True):
        pid = row["page_id"]
        if pid == exclude_page_id or stems.get(pid) in holdout:
            continue
        img = processed_dir / f"{pid}.jpg"
        if not img.exists():
            continue
        messages.append(
            Message("user", [Part.of_image(img), Part.of_text("Transcribe this page.")])
        )
        messages.append(Message("assistant", [Part.of_text(gold_to_json(row["gold_text"]))]))
        if len(messages) >= 2 * k:
            break
    return messages


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_lines_json(text: str) -> list[dict]:
    """Parse ``{"lines": [...]}`` leniently; fall back to plain lines if the model ignored JSON."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.MULTILINE).strip()
    m = _JSON_BLOCK.search(cleaned)
    if m:
        try:
            obj = json.loads(m.group(0))
            lines = obj.get("lines", obj if isinstance(obj, list) else [])
            out = []
            for i, ln in enumerate(lines):
                if isinstance(ln, str):
                    out.append({"n": i + 1, "text": ln, "confidence": "medium"})
                elif isinstance(ln, dict) and "text" in ln:
                    out.append(
                        {
                            "n": int(ln.get("n", i + 1)),
                            "text": str(ln["text"]),
                            "confidence": str(ln.get("confidence", "medium")).lower(),
                        }
                    )
            if out:
                return out
        except (json.JSONDecodeError, AttributeError, ValueError):
            pass
    return [
        {"n": i + 1, "text": ln.strip(), "confidence": "medium"}
        for i, ln in enumerate(cleaned.splitlines())
        if ln.strip()
    ]
