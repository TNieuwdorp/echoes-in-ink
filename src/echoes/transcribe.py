"""Stage 2: run pages through a vision engine, N samples each, and store every line."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import polars as pl
from rich.console import Console

from . import evaluate, prompting, schema
from .engines import Engine, Message, Part

console = Console()


def page_context(pages: pl.DataFrame, letters: pl.DataFrame, page_id: str) -> str:
    row = pages.filter(pl.col("page_id") == page_id)
    if row.is_empty():
        return ""
    r = row.row(0, named=True)
    bits = []
    if r["letter_id"]:
        bits.append(f"Letter id: {r['letter_id']}.")
    if r["page_no"]:
        bits.append(f"This is page {r['page_no']} of the letter.")
        if r["page_no"] > 1 and not letters.is_empty():
            prev = pages.filter(
                (pl.col("letter_id") == r["letter_id"]) & (pl.col("page_no") == r["page_no"] - 1)
            )
            if not prev.is_empty():
                prev_text = letters.filter(pl.col("page_id") == prev["page_id"][0])
                if not prev_text.is_empty():
                    tail = prev_text["text_final"][0].splitlines()[-3:]
                    bits.append("The previous page ended with:\n" + "\n".join(tail))
    return "\n".join(bits)


def build_messages(
    target_page: Path,
    bands: list[Path],
    examples: list[Message],
    context: str,
) -> list[Message]:
    parts = [Part.of_image(target_page)]
    for b in bands:
        parts.append(Part.of_image(b))
    intro = "Transcribe this page."
    if bands:
        intro += f" The first image is the full page; the next {len(bands)} images are zoomed crops of the same page, top to bottom."
    if context:
        intro += "\n" + context
    parts.append(Part.of_text(intro))
    return [*examples, Message("user", parts)]


def transcribe_pages(
    engine: Engine,
    page_ids: list[str],
    *,
    samples: int = 1,
    temperature: float = 0.0,
    with_bands: bool = False,
    few_shot: int = 2,
    thinking: bool = False,
    processed_dir: Path | None = None,
    gold_dir: Path | None = None,
) -> pl.DataFrame:
    processed_dir = processed_dir or schema.data_path("processed")
    gold_dir = gold_dir or schema.data_path("gold")
    pages = schema.read_or_empty(schema.data_path("pages.parquet"), schema.PAGES)
    letters = schema.read_or_empty(schema.data_path("letters.parquet"), schema.LETTERS)
    gold = evaluate.load_gold(gold_dir, pages)
    template, version = prompting.load_prompt("transcribe")
    system = prompting.render(template, names="\n".join(prompting.load_names()) or "(none yet)")
    variant = "page+bands" if with_bands else "page"

    rows = []
    for pid in page_ids:
        page_img = processed_dir / f"{pid}.jpg"
        if not page_img.exists():
            console.print(f"[yellow]skip {pid}: not preprocessed[/]")
            continue
        bands = sorted(processed_dir.glob(f"{pid}_band*.jpg")) if with_bands else []
        examples = prompting.few_shot_examples(
            pages, gold, processed_dir, pid, gold_dir, k=few_shot
        )
        messages = build_messages(page_img, bands, examples, page_context(pages, letters, pid))
        for s in range(samples):
            temp = 0.0 if s == 0 and samples > 1 else temperature
            reply = engine.chat(
                system, messages, temperature=temp, max_tokens=6000, thinking=thinking
            )
            lines = prompting.parse_lines_json(reply.text)
            now = datetime.now()
            for ln in lines:
                rows.append(
                    {
                        "page_id": pid,
                        "engine": engine.name,
                        "model": reply.model,
                        "prompt_version": version,
                        "variant": variant,
                        "sample_no": s,
                        "line_no": ln["n"],
                        "text": ln["text"],
                        "confidence": ln["confidence"],
                        "created_at": now,
                    }
                )
            console.print(
                f"{pid} sample {s}: {len(lines)} lines, {reply.input_tokens} in / {reply.output_tokens} out tokens"
            )
    new = (
        pl.DataFrame(rows, schema=schema.TRANSCRIPTIONS)
        if rows
        else schema.empty(schema.TRANSCRIPTIONS)
    )
    path = schema.data_path("transcriptions.parquet")
    existing = schema.read_or_empty(path, schema.TRANSCRIPTIONS)
    merged = schema.upsert(
        existing, new, ["page_id", "engine", "model", "prompt_version", "variant", "sample_no"]
    )
    schema.write(merged, path)
    return new
