"""Stage 3: merge several readings of a page into one text with uncertainty marks.

1. Pick a reference reading (the greedy sample of the preferred engine when present).
2. Align every other reading's lines to the reference lines (monotone DP on fuzzy ratio).
3. Vote per word position; disagreements become alternatives.
4. Optionally let a text model resolve the alternatives with Dutch knowledge.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher

import polars as pl
from rapidfuzz import fuzz

from . import prompting, schema
from .engines import Engine, Message, Part


@dataclass
class VotedLine:
    n: int
    tokens: list[str]
    alternatives: dict[int, list[str]] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return " ".join(self.tokens)

    def marked(self) -> str:
        out = []
        for i, tok in enumerate(self.tokens):
            alts = self.alternatives.get(i)
            out.append("{" + "|".join([tok, *alts]) + "}" if alts else tok)
        return " ".join(out)

    def uncertain(self) -> list[dict]:
        return [
            {"line_no": self.n, "word": self.tokens[i], "alternatives": alts}
            for i, alts in sorted(self.alternatives.items())
        ]


def align_lines(ref: list[str], hyp: list[str], min_ratio: int = 45) -> list[int | None]:
    """For each ref line, the index of the matching hyp line (monotone), or None."""
    n, m = len(ref), len(hyp)
    if not n or not m:
        return [None] * n
    sim = [[fuzz.ratio(r, h) for h in hyp] for r in ref]
    # Needleman-Wunsch style DP maximising total similarity of matched pairs.
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            match = dp[i - 1][j - 1] + (sim[i - 1][j - 1] if sim[i - 1][j - 1] >= min_ratio else 0)
            dp[i][j] = max(match, dp[i - 1][j], dp[i][j - 1])
    out: list[int | None] = [None] * n
    i, j = n, m
    while i > 0 and j > 0:
        if sim[i - 1][j - 1] >= min_ratio and dp[i][j] == dp[i - 1][j - 1] + sim[i - 1][j - 1]:
            out[i - 1] = j - 1
            i, j = i - 1, j - 1
        elif dp[i][j] == dp[i - 1][j]:
            i -= 1
        else:
            j -= 1
    return out


def vote_tokens(ref_tokens: list[str], hyps: list[list[str]]) -> VotedLine:
    votes: list[Counter] = [Counter({tok: 1}) for tok in ref_tokens]
    for hyp in hyps:
        sm = SequenceMatcher(None, ref_tokens, hyp, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for k in range(i2 - i1):
                    votes[i1 + k][ref_tokens[i1 + k]] += 1
            elif tag == "replace" and (i2 - i1) == (j2 - j1):
                for k in range(i2 - i1):
                    votes[i1 + k][hyp[j1 + k]] += 1
            # insertions/deletions/unequal replaces are not counted as evidence
    tokens, alternatives = [], {}
    for i, c in enumerate(votes):
        best, best_n = c.most_common(1)[0]
        total = sum(c.values())
        if c[ref_tokens[i]] == best_n:
            best = ref_tokens[i]  # tie goes to the reference reading
        tokens.append(best)
        others = [t for t, _ in c.most_common() if t != best]
        if others or best_n < total:
            alternatives[i] = others
    return VotedLine(0, tokens, alternatives)


def vote_page(readings: list[list[str]]) -> list[VotedLine]:
    """``readings[0]`` is the reference; each reading is a list of line strings."""
    ref = readings[0]
    aligned = [align_lines(ref, hyp) for hyp in readings[1:]]
    out = []
    for i, line in enumerate(ref):
        ref_tokens = line.split()
        hyps = []
        for hyp, al in zip(readings[1:], aligned, strict=True):
            j = al[i]
            if j is not None:
                hyps.append(hyp[j].split())
        voted = vote_tokens(ref_tokens, hyps) if ref_tokens else VotedLine(0, [])
        voted.n = i + 1
        out.append(voted)
    return out


def readings_for_page(
    tr: pl.DataFrame, page_id: str, prefer_engine: str = "local"
) -> list[list[str]]:
    sub = tr.filter(pl.col("page_id") == page_id)
    if sub.is_empty():
        return []
    keys = ["engine", "model", "prompt_version", "variant", "sample_no"]
    grouped = (
        sub.sort([*keys, "line_no"])
        .group_by(keys, maintain_order=True)
        .agg(pl.col("text").alias("lines"))
    )
    # reference first: preferred engine, greedy sample, then the rest in stable order
    grouped = grouped.with_columns(
        (
            (pl.col("engine") != prefer_engine).cast(pl.Int8) * 10
            + pl.col("sample_no").cast(pl.Int8)
        ).alias("rank")
    ).sort("rank")
    return [list(x) for x in grouped["lines"].to_list()]


def llm_correct(
    engine: Engine, voted: list[VotedLine], context: str = ""
) -> tuple[list[str], list[dict]]:
    template, _ = prompting.load_prompt("correct")
    system = prompting.render(template, names="\n".join(prompting.load_names()) or "(none yet)")
    body = "\n".join(f"{v.n}: {v.marked()}" for v in voted)
    user = (context + "\n\n" if context else "") + "Transcription with alternatives:\n" + body
    reply = engine.chat(
        system,
        [Message("user", [Part.of_text(user)])],
        temperature=0.0,
        max_tokens=6000,
        thinking=True,
    )
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", reply.text.strip(), flags=re.MULTILINE)
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not m:
        return [v.text for v in voted], [u for v in voted for u in v.uncertain()]
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return [v.text for v in voted], [u for v in voted for u in v.uncertain()]
    by_n = {
        int(ln["n"]): str(ln["text"]) for ln in obj.get("lines", []) if "n" in ln and "text" in ln
    }
    lines = [by_n.get(v.n, v.text) for v in voted]
    uncertain = [
        {
            "line_no": int(u.get("n", 0)),
            "word": str(u.get("word", "")),
            "alternatives": [str(a) for a in u.get("alternatives", [])],
        }
        for u in obj.get("uncertain", [])
    ]
    return lines, uncertain


def reconcile_page(
    page_id: str, corrector: Engine | None = None, prefer_engine: str = "local"
) -> dict | None:
    tr = schema.read_or_empty(schema.data_path("transcriptions.parquet"), schema.TRANSCRIPTIONS)
    readings = readings_for_page(tr, page_id, prefer_engine)
    if not readings:
        return None
    voted = vote_page(readings)
    if corrector is not None:
        lines, uncertain = llm_correct(corrector, voted)
    else:
        lines = [v.text for v in voted]
        uncertain = [u for v in voted for u in v.uncertain()]
    return {
        "page_id": page_id,
        "text_final": "\n".join(lines),
        "text_source": "auto",
        "uncertain_spans": uncertain,
        "reviewed_by": None,
        "reviewed_at": None,
        "updated_at": datetime.now(),
    }


def reconcile_pages(
    page_ids: list[str], corrector: Engine | None = None, prefer_engine: str = "local"
) -> pl.DataFrame:
    path = schema.data_path("letters.parquet")
    existing = schema.read_or_empty(path, schema.LETTERS)
    protected = set(existing.filter(pl.col("text_source").is_in(["reviewed", "gold"]))["page_id"])
    rows = []
    for pid in page_ids:
        if pid in protected:
            continue  # never overwrite a human's work with an automatic result
        row = reconcile_page(pid, corrector, prefer_engine)
        if row:
            rows.append(row)
    new = pl.DataFrame(rows, schema=schema.LETTERS) if rows else schema.empty(schema.LETTERS)
    merged = schema.upsert(existing, new, ["page_id"])
    schema.write(merged, path)
    return new
