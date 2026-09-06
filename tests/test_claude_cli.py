import json
import os
import stat
from pathlib import Path

from echoes.engines import Message, Part, get_engine
from echoes.engines.claude_cli import ClaudeCliEngine
from echoes.prompting import parse_lines_json

FAKE = """#!/usr/bin/env bash
# record argv and the staged files, then answer like `claude -p --output-format json`
python3 - "$@" <<'PY'
import json, os, sys
json.dump({"argv": sys.argv[1:], "cwd_files": sorted(os.listdir("."))},
          open(os.environ["FAKE_CLAUDE_RECORD"], "w"))
PY
cat <<'JSON'
{"type":"result","subtype":"success","is_error":false,"num_turns":3,"session_id":"x",
 "result":"{\\"lines\\": []}","total_cost_usd":0.0421,
 "usage":{"input_tokens":5120,"output_tokens":410},
 "modelUsage":{"claude-opus-5":{"inputTokens":5120}},
 "structured_output":{"lines":[{"n":1,"text":"Lieve Ouders en Han,","confidence":"high"},
                               {"n":2,"text":"Wij zijn goed [?]","confidence":"low"}]}}
JSON
"""


def _install_fake_claude(tmp_path: Path, monkeypatch) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "claude"
    exe.write_text(FAKE)
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_CLAUDE_RECORD", str(record))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return record


def test_cli_engine_stages_images_and_parses_structured_output(tmp_path, fixtures, monkeypatch):
    record = _install_fake_claude(tmp_path, monkeypatch)
    engine = get_engine("claude")
    assert isinstance(engine, ClaudeCliEngine)
    messages = [
        Message(
            "user",
            [Part.of_image(fixtures / "1945-03-15_p1.jpg"), Part.of_text("Transcribe this page.")],
        ),
        Message(
            "assistant",
            [Part.of_text('{"lines": [{"n": 1, "text": "voorbeeld", "confidence": "high"}]}')],
        ),
        Message(
            "user",
            [
                Part.of_image(fixtures / "1945-03-15_p2.jpg"),
                Part.of_image(fixtures / "1945-03-15_p1_binder.jpg"),
                Part.of_text("Letter dated 15 March 1945."),
            ],
        ),
    ]
    reply = engine.chat("SYSTEM PROMPT", messages, thinking=True)

    rec = json.loads(record.read_text())
    argv = rec["argv"]
    assert argv[0] == "-p"
    prompt = argv[1]
    assert "[Example 1] Read `example1_01.jpg`." in prompt
    assert "[Correct transcription for example 1]" in prompt and "voorbeeld" in prompt
    assert "[Task] Read `page_02.jpg`, `page_03.jpg`." in prompt
    assert "Letter dated 15 March 1945." in prompt
    assert rec["cwd_files"] == ["example1_01.jpg", "page_02.jpg", "page_03.jpg"]

    flags = dict(zip(argv[2::2], argv[3::2], strict=False))
    assert flags["--model"] == "claude-opus-5"
    assert flags["--system-prompt"] == "SYSTEM PROMPT"
    assert flags["--tools"] == "Read" and flags["--allowedTools"] == "Read"
    assert flags["--permission-prompts"] == "none"
    assert flags["--output-format"] == "json"
    assert flags["--effort"] == "high"
    assert json.loads(flags["--json-schema"])["required"] == ["lines"]
    assert "--safe-mode" in argv and "--no-session-persistence" in argv and "--bare" not in argv

    lines = parse_lines_json(reply.text)
    assert [ln["text"] for ln in lines] == ["Lieve Ouders en Han,", "Wij zijn goed [?]"]
    assert lines[1]["confidence"] == "low"
    assert reply.model == "claude-opus-5"
    assert (reply.input_tokens, reply.output_tokens, reply.cost_usd) == (5120, 410, 0.0421)


def test_registry_prefers_sdk_when_key_present(tmp_path, monkeypatch):
    _install_fake_claude(tmp_path, monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    from echoes.engines.anthropic_engine import AnthropicEngine

    assert isinstance(get_engine("claude"), AnthropicEngine)
    assert isinstance(get_engine("claude-cli"), ClaudeCliEngine)
