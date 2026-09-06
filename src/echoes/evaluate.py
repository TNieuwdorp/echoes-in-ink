"""Evaluation harness: CER / WER / name recall against gold transcriptions.

Gold files live in ``data/gold/<image-stem>.txt`` (matched to pages by filename stem) or
``data/gold/<page_id>.txt``. Lines starting with ``#`` are comments. ``[?]`` marks an
illegible word and ``[gecensureerd]`` a censored span; both conventions are shared with
the model prompt so they compare equal.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import jiwer
import polars as pl

from . import schema

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s\[\]?'-]", re.UNICODE)


def normalise(text: str, *, casefold: bool = False, strip_punct: bool = False) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("­", "")  # soft hyphen
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    text = " ".join(lines)
    # join hyphenated line breaks written as "trof-" + "fen"
    text = re.sub(r"(\w)- (\w)", r"\1\2", text)
    if strip_punct:
        text = _PUNCT.sub(" ", text)
    if casefold:
        text = text.casefold()
    return _WS.sub(" ", text).strip()


def cer(ref: str, hyp: str) -> float:
    ref_n, hyp_n = normalise(ref), normalise(hyp)
    if not ref_n:
        return 0.0 if not hyp_n else 1.0
    return float(jiwer.cer(ref_n, hyp_n or " "))


def wer(ref: str, hyp: str) -> float:
    ref_n = normalise(ref, casefold=True, strip_punct=True)
    hyp_n = normalise(hyp, casefold=True, strip_punct=True)
    if not ref_n:
        return 0.0 if not hyp_n else 1.0
    return float(jiwer.wer(ref_n, hyp_n or " "))


def proper_nouns(text: str) -> set[str]:
    """Capitalised tokens that are not sentence-initial: a cheap proxy for names."""
    tokens = normalise(text, strip_punct=False).split()
    out = set()
    for i, tok in enumerate(tokens):
        bare = tok.strip(".,;:!?()\"'")
        if len(bare) < 3 or not bare[0].isupper() or bare.isupper():
            continue
        prev = tokens[i - 1] if i else "."
        if prev.endswith((".", "!", "?", ":")):
            continue
        out.add(bare)
    return out


def name_recall(ref: str, hyp: str) -> float | None:
    names = proper_nouns(ref)
    if not names:
        return None
    hyp_tokens = {t.strip(".,;:!?()\"'") for t in normalise(hyp).split()}
    return len(names & hyp_tokens) / len(names)


def load_gold(gold_dir: Path, pages: pl.DataFrame) -> pl.DataFrame:
    """Return ``page_id, gold_text`` for every gold file that matches a page."""
    if not gold_dir.exists() or pages.is_empty():
        return pl.DataFrame(schema={"page_id": pl.Utf8, "gold_text": pl.Utf8})
    by_stem = {
        Path(f).stem: pid for f, pid in zip(pages["filename"], pages["page_id"], strict=True)
    }
    ids = set(pages["page_id"])
    rows = []
    for txt in sorted(gold_dir.glob("*.txt")):
        pid = by_stem.get(txt.stem) or (txt.stem if txt.stem in ids else None)
        if pid is None:
            continue
        rows.append({"page_id": pid, "gold_text": txt.read_text(encoding="utf-8")})
    return pl.DataFrame(rows, schema={"page_id": pl.Utf8, "gold_text": pl.Utf8})


def _join_lines(df: pl.DataFrame) -> pl.DataFrame:
    """Collapse transcription lines into one text per (page, engine, model, prompt, variant, sample)."""
    keys = ["page_id", "engine", "model", "prompt_version", "variant", "sample_no"]
    return (
        df.sort([*keys, "line_no"])
        .group_by(keys, maintain_order=True)
        .agg(pl.col("text").str.join("\n").alias("hyp"))
    )


def score_frame(hyps: pl.DataFrame, gold: pl.DataFrame) -> pl.DataFrame:
    """Attach cer/wer/name_recall columns to a frame that has ``page_id`` and ``hyp``."""
    joined = hyps.join(gold, on="page_id", how="inner")
    if joined.is_empty():
        return joined.with_columns(
            pl.lit(None, pl.Float64).alias("cer"),
            pl.lit(None, pl.Float64).alias("wer"),
            pl.lit(None, pl.Float64).alias("name_recall"),
        )
    return joined.with_columns(
        pl.struct(["gold_text", "hyp"])
        .map_elements(lambda s: cer(s["gold_text"], s["hyp"]), return_dtype=pl.Float64)
        .alias("cer"),
        pl.struct(["gold_text", "hyp"])
        .map_elements(lambda s: wer(s["gold_text"], s["hyp"]), return_dtype=pl.Float64)
        .alias("wer"),
        pl.struct(["gold_text", "hyp"])
        .map_elements(lambda s: name_recall(s["gold_text"], s["hyp"]), return_dtype=pl.Float64)
        .alias("name_recall"),
    )


def leaderboard(
    transcriptions: pl.DataFrame, letters: pl.DataFrame, gold: pl.DataFrame
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Return (summary per system, per-page detail).

    Systems are every (engine, model, prompt_version, variant) in transcriptions, scored
    per sample and averaged, plus ``final`` for the current text in letters.parquet.
    """
    parts = []
    if not transcriptions.is_empty():
        parts.append(score_frame(_join_lines(transcriptions), gold))
    if not letters.is_empty():
        final = letters.select(
            "page_id",
            pl.lit("final").alias("engine"),
            pl.col("text_source").alias("model"),
            pl.lit("-").alias("prompt_version"),
            pl.lit("-").alias("variant"),
            pl.lit(0, pl.Int32).alias("sample_no"),
            pl.col("text_final").alias("hyp"),
        )
        parts.append(score_frame(final, gold))
    if not parts:
        empty = pl.DataFrame(schema={"engine": pl.Utf8})
        return empty, empty
    detail = pl.concat(parts, how="vertical_relaxed")
    summary = (
        detail.group_by(["engine", "model", "prompt_version", "variant"])
        .agg(
            pl.col("page_id").n_unique().alias("pages"),
            pl.len().alias("samples"),
            pl.col("cer").mean().alias("cer"),
            pl.col("wer").mean().alias("wer"),
            pl.col("name_recall").mean().alias("name_recall"),
        )
        .sort("cer")
    )
    return summary, detail.sort(["cer"], descending=True)


def run(gold_dir: Path | None = None) -> tuple[pl.DataFrame, pl.DataFrame]:
    gold_dir = gold_dir or schema.data_path("gold")
    pages = schema.read_or_empty(schema.data_path("pages.parquet"), schema.PAGES)
    gold = load_gold(gold_dir, pages)
    tr = schema.read_or_empty(schema.data_path("transcriptions.parquet"), schema.TRANSCRIPTIONS)
    letters = schema.read_or_empty(schema.data_path("letters.parquet"), schema.LETTERS)
    return leaderboard(tr, letters, gold)
