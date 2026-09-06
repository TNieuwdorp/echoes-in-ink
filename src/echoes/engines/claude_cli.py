"""Cloud ceiling without an API key: Claude through the Claude Code CLI.

``claude -p`` runs on the user's subscription login. Images cannot be attached to a print-mode
prompt, so the page and few-shot images are staged in a scratch directory and the prompt tells
the model which files to read with the ``Read`` tool (the only tool enabled). The multi-turn
few-shot layout of the other engines is flattened into one prompt. Structured output comes
back through ``--json-schema`` as ``structured_output``; the ``result`` text is the fallback.

``--safe-mode`` keeps the login but skips CLAUDE.md, hooks and plugins. ``--bare`` must not be
used here: it only reads ``ANTHROPIC_API_KEY``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .base import Message, Reply

LINES_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "text": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["n", "text", "confidence"],
            },
        }
    },
    "required": ["lines"],
}


@dataclass
class ClaudeCliEngine:
    name: str = "claude"
    model: str = "claude-opus-5"
    fallback_model: str = "claude-opus-4-8"
    binary: str = "claude"
    max_turns: int = 8
    timeout_s: int = 900
    workdir: Path | None = None  # parent for the per-call staging directory
    json_schema: dict = field(default_factory=lambda: LINES_SCHEMA)

    def command(self, prompt: str, system: str, staging: Path, *, thinking: bool) -> list[str]:
        return [
            self.binary,
            "-p",
            prompt,
            "--model",
            self.model,
            "--fallback-model",
            self.fallback_model,
            "--system-prompt",
            system,
            "--tools",
            "Read",
            "--allowedTools",
            "Read",
            "--permission-prompts",
            "none",
            "--max-turns",
            str(self.max_turns),
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(self.json_schema),
            "--effort",
            "high" if thinking else "medium",
            "--safe-mode",
            "--no-session-persistence",
            "--add-dir",
            str(staging),
        ]

    @staticmethod
    def flatten(messages: list[Message], staging: Path) -> str:
        """Turn image/text turns into one prompt; copy images into ``staging``."""
        user_turns = sum(1 for m in messages if m.role == "user")
        examples = user_turns - 1
        blocks = [
            "Use the Read tool to look at every image file named below, in order, before you "
            "answer. The files are in the current directory.",
        ]
        example_no = 0
        image_no = 0
        for m in messages:
            if m.role == "user":
                is_task = example_no == examples
                label = "[Task]" if is_task else f"[Example {example_no + 1}]"
                texts, reads = [], []
                for part in m.parts:
                    if part.kind == "image" and part.path is not None:
                        image_no += 1
                        prefix = "page" if is_task else f"example{example_no + 1}"
                        dst = staging / f"{prefix}_{image_no:02d}{part.path.suffix.lower()}"
                        shutil.copyfile(part.path, dst)
                        reads.append(f"`{dst.name}`")
                    else:
                        texts.append(part.text)
                line = f"{label} Read {', '.join(reads)}." if reads else label
                blocks.append("\n".join([line, *texts]).strip())
            else:
                blocks.append(
                    f"[Correct transcription for example {example_no + 1}]\n"
                    + "\n".join(p.text for p in m.parts if p.kind == "text")
                )
                example_no += 1
        blocks.append(
            "Answer with the JSON object described in the system prompt and nothing else."
        )
        return "\n\n".join(blocks)

    def chat(
        self,
        system: str,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        thinking: bool = False,
    ) -> Reply:
        # temperature and max_tokens are not controllable through the CLI; effort steers depth.
        with tempfile.TemporaryDirectory(prefix="echoes-claude-", dir=self.workdir) as tmp:
            staging = Path(tmp)
            prompt = self.flatten(messages, staging)
            proc = subprocess.run(
                self.command(prompt, system, staging, thinking=thinking),
                cwd=staging,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
        if proc.returncode != 0 and not proc.stdout.strip():
            raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr.strip()[:2000]}")
        result = _parse_result(proc.stdout)
        if result.get("is_error"):
            raise RuntimeError(f"claude reported an error: {result.get('result')}")
        structured = result.get("structured_output")
        text = (
            json.dumps(structured, ensure_ascii=False)
            if structured
            else str(result.get("result", ""))
        )
        usage = result.get("usage") or {}
        model_usage = result.get("modelUsage") or {}
        model = next(iter(model_usage), self.model) if isinstance(model_usage, dict) else self.model
        return Reply(
            text=text,
            model=model,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            cost_usd=result.get("total_cost_usd"),
        )


def _parse_result(stdout: str) -> dict:
    stripped = stdout.strip()
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        if start < 0:
            raise RuntimeError(f"claude printed no JSON result: {stripped[:500]!r}") from None
        obj = json.loads(stripped[start:])
    if isinstance(obj, list):  # stream-style output: the result object comes last
        obj = next((o for o in reversed(obj) if o.get("type") == "result"), obj[-1])
    return obj
