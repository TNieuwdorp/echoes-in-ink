"""Polars schemas and Parquet helpers.

Every stage of the pipeline reads and writes one of the frames below. Keeping the
schemas in one place means a stage can be re-run in isolation and the frames stay
joinable on ``page_id`` (sha256 prefix of the original image bytes).
"""

from __future__ import annotations

import os
from pathlib import Path

import polars as pl

DATA_DIR = Path(os.environ.get("ECHOES_DATA", "data"))


def data_path(name: str) -> Path:
    return DATA_DIR / name


PAGES = {
    "page_id": pl.Utf8,
    "source_path": pl.Utf8,
    "filename": pl.Utf8,
    "letter_id": pl.Utf8,
    "page_no": pl.Int32,
    "width": pl.Int32,
    "height": pl.Int32,
    "captured_at": pl.Datetime("us"),
    "camera": pl.Utf8,
    "ingested_at": pl.Datetime("us"),
}

# One row per model output line. Every sample of every engine is kept so that
# engines, prompts and preprocessing variants can be compared afterwards.
TRANSCRIPTIONS = {
    "page_id": pl.Utf8,
    "engine": pl.Utf8,
    "model": pl.Utf8,
    "prompt_version": pl.Utf8,
    "variant": pl.Utf8,  # e.g. "page", "page+bands"
    "sample_no": pl.Int32,
    "line_no": pl.Int32,
    "text": pl.Utf8,
    "confidence": pl.Utf8,  # high | medium | low
    "created_at": pl.Datetime("us"),
}

# The current best text per page, plus where it came from.
LETTERS = {
    "page_id": pl.Utf8,
    "text_final": pl.Utf8,
    "text_source": pl.Utf8,  # auto | reviewed | gold
    "uncertain_spans": pl.List(
        pl.Struct(
            {
                "line_no": pl.Int32,
                "word": pl.Utf8,
                "alternatives": pl.List(pl.Utf8),
            }
        )
    ),
    "reviewed_by": pl.Utf8,
    "reviewed_at": pl.Datetime("us"),
    "updated_at": pl.Datetime("us"),
}

# Letter-level metadata, set in the review UI or derived from filenames.
LETTER_META = {
    "letter_id": pl.Utf8,
    "date": pl.Date,
    "place": pl.Utf8,
    "recipient": pl.Utf8,
    "title": pl.Utf8,
    "notes": pl.Utf8,
}

ENTITIES = {
    "letter_id": pl.Utf8,
    "kind": pl.Utf8,  # person | place
    "name": pl.Utf8,
    "canonical": pl.Utf8,
    "detail": pl.Utf8,  # role_guess for people, modern_name for places
    "context": pl.Utf8,
}

EVENTS = {
    "letter_id": pl.Utf8,
    "date": pl.Date,
    "date_text": pl.Utf8,
    "description": pl.Utf8,
    "category": pl.Utf8,  # letter | travel | military | health | family | daily_life | news
    "source": pl.Utf8,  # letter_date | extracted | context
}

SUMMARIES = {
    "letter_id": pl.Utf8,
    "summary_nl": pl.Utf8,
    "summary_en": pl.Utf8,
    "mood": pl.Utf8,
    "notable_quotes": pl.List(pl.Utf8),
    "model": pl.Utf8,
    "created_at": pl.Datetime("us"),
}


def empty(schema: dict) -> pl.DataFrame:
    return pl.DataFrame(schema=schema)


def read_or_empty(path: Path, schema: dict) -> pl.DataFrame:
    if path.exists():
        return pl.read_parquet(path)
    return empty(schema)


def upsert(existing: pl.DataFrame, new: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    """Replace rows in ``existing`` that share ``keys`` with rows from ``new``."""
    if existing.is_empty():
        return new
    if new.is_empty():
        return existing
    keep = existing.join(new.select(keys).unique(), on=keys, how="anti")
    return pl.concat([keep, new.select(existing.columns)], how="vertical_relaxed")


def write(df: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)
