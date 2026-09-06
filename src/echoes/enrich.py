"""Stage 5: extract people, places, events and summaries per letter with a text model."""

from __future__ import annotations

import json
import re
from datetime import date, datetime

import polars as pl
from rapidfuzz import fuzz, process

from . import prompting, schema
from .engines import Engine, Message, Part


def letter_texts(pages: pl.DataFrame, letters: pl.DataFrame) -> pl.DataFrame:
    """One row per letter_id with the pages' final text joined in page order."""
    return (
        pages.filter(pl.col("letter_id").is_not_null())
        .join(letters.select("page_id", "text_final"), on="page_id", how="inner")
        .sort(["letter_id", "page_no"])
        .group_by("letter_id", maintain_order=True)
        .agg(pl.col("text_final").str.join("\n").alias("text"), pl.col("page_id").alias("page_ids"))
    )


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = re.match(r"^(\d{4})-(\d{2})$", s)
    if m:
        return date(int(m[1]), int(m[2]), 1)
    m = re.match(r"^(\d{4})$", s)
    return date(int(m[1]), 1, 1) if m else None


def extract_letter(engine: Engine, letter_id: str, text: str, letter_date: str | None) -> dict:
    template, _ = prompting.load_prompt("extract")
    system = template
    user = f"Letter id: {letter_id}\nLetter date: {letter_date or 'unknown'}\n\nText:\n{text}"
    reply = engine.chat(
        system,
        [Message("user", [Part.of_text(user)])],
        temperature=0.0,
        max_tokens=6000,
        thinking=True,
    )
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", reply.text.strip(), flags=re.MULTILINE)
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    obj = json.loads(m.group(0)) if m else {}
    obj["_model"] = reply.model
    return obj


def canonicalise(names: list[str], threshold: int = 88) -> dict[str, str]:
    """Cluster spelling variants (Wim / W. / Willem is *not* merged; Alloosel / Allosel is)."""
    canon: dict[str, str] = {}
    representatives: list[str] = []
    for name in sorted(set(names), key=lambda s: (-len(s), s)):
        match = process.extractOne(
            name, representatives, scorer=fuzz.token_sort_ratio, score_cutoff=threshold
        )
        if match:
            canon[name] = match[0]
        else:
            representatives.append(name)
            canon[name] = name
    return canon


def enrich(engine: Engine, letter_ids: list[str] | None = None) -> None:
    pages = schema.read_or_empty(schema.data_path("pages.parquet"), schema.PAGES)
    letters = schema.read_or_empty(schema.data_path("letters.parquet"), schema.LETTERS)
    meta = schema.read_or_empty(schema.data_path("letter_meta.parquet"), schema.LETTER_META)
    texts = letter_texts(pages, letters)
    if letter_ids:
        texts = texts.filter(pl.col("letter_id").is_in(letter_ids))
    dates = dict(zip(meta["letter_id"], meta["date"], strict=True)) if not meta.is_empty() else {}

    ent_rows, ev_rows, sum_rows = [], [], []
    now = datetime.now()
    for row in texts.iter_rows(named=True):
        lid = row["letter_id"]
        ldate = dates.get(lid) or _parse_date(lid)
        obj = extract_letter(engine, lid, row["text"], ldate.isoformat() if ldate else None)
        for p in obj.get("people", []):
            ent_rows.append(
                {
                    "letter_id": lid,
                    "kind": "person",
                    "name": p.get("name", ""),
                    "canonical": None,
                    "detail": p.get("role_guess"),
                    "context": p.get("context"),
                }
            )
        for p in obj.get("places", []):
            ent_rows.append(
                {
                    "letter_id": lid,
                    "kind": "place",
                    "name": p.get("name", ""),
                    "canonical": None,
                    "detail": p.get("modern_name"),
                    "context": None,
                }
            )
        if ldate:
            ev_rows.append(
                {
                    "letter_id": lid,
                    "date": ldate,
                    "date_text": ldate.isoformat(),
                    "description": f"Brief geschreven ({lid})",
                    "category": "letter",
                    "source": "letter_date",
                }
            )
        for e in obj.get("events", []):
            ev_rows.append(
                {
                    "letter_id": lid,
                    "date": _parse_date(e.get("date")),
                    "date_text": e.get("date_text") or e.get("date"),
                    "description": e.get("description", ""),
                    "category": e.get("category", "daily_life"),
                    "source": "extracted",
                }
            )
        sum_rows.append(
            {
                "letter_id": lid,
                "summary_nl": obj.get("summary_nl"),
                "summary_en": obj.get("summary_en"),
                "mood": obj.get("mood"),
                "notable_quotes": obj.get("notable_quotes", []),
                "model": obj.get("_model"),
                "created_at": now,
            }
        )

    ents = (
        pl.DataFrame(ent_rows, schema=schema.ENTITIES)
        if ent_rows
        else schema.empty(schema.ENTITIES)
    )
    if not ents.is_empty():
        canon = canonicalise(ents["name"].to_list())
        ents = ents.with_columns(
            pl.col("name").replace_strict(canon, default=pl.col("name")).alias("canonical")
        )
    for name, df, sch in (
        ("entities", ents, schema.ENTITIES),
        (
            "events",
            pl.DataFrame(ev_rows, schema=schema.EVENTS) if ev_rows else schema.empty(schema.EVENTS),
            schema.EVENTS,
        ),
        (
            "summaries",
            pl.DataFrame(sum_rows, schema=schema.SUMMARIES)
            if sum_rows
            else schema.empty(schema.SUMMARIES),
            schema.SUMMARIES,
        ),
    ):
        path = schema.data_path(f"{name}.parquet")
        existing = schema.read_or_empty(path, sch)
        done = set(df["letter_id"]) if not df.is_empty() else set()
        keep = existing.filter(~pl.col("letter_id").is_in(list(done))) if done else existing
        schema.write(
            pl.concat([keep, df], how="vertical_relaxed") if not df.is_empty() else keep, path
        )
