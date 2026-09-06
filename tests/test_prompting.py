from echoes import prompting


def test_parse_lines_json_variants():
    good = '{"lines": [{"n": 1, "text": "a", "confidence": "high"}, {"n": 2, "text": "b"}]}'
    out = prompting.parse_lines_json(good)
    assert [ln["text"] for ln in out] == ["a", "b"]
    assert out[1]["confidence"] == "medium"
    fenced = "```json\n" + good + "\n```"
    assert len(prompting.parse_lines_json(fenced)) == 2
    plain = "regel een\nregel twee\n"
    assert [ln["text"] for ln in prompting.parse_lines_json(plain)] == ["regel een", "regel twee"]


def test_prompt_renders_names():
    template, version = prompting.load_prompt("transcribe")
    assert len(version) == 8
    rendered = prompting.render(template, names="Han\nFrits")
    assert "Han\nFrits" in rendered and "{names}" not in rendered
    assert '{"lines": [' in rendered  # JSON example survives rendering


def test_gold_to_json_skips_comments():
    j = prompting.gold_to_json("# note\nline one\n\nline two\n")
    assert '"n": 2' in j and "note" not in j
