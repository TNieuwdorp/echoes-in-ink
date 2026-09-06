"""Review-mode backend: serves the Parquet frames as Arrow IPC and accepts corrections.

Run with ``echoes serve``. The Svelte app in ``ui/`` talks to these endpoints while you
work; the family site uses the exported Parquet files instead and needs no server.
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

import polars as pl
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import schema

app = FastAPI(title="Echoes in Ink")

FRAMES = {
    "pages": schema.PAGES,
    "letters": schema.LETTERS,
    "letter_meta": schema.LETTER_META,
    "transcriptions": schema.TRANSCRIPTIONS,
    "entities": schema.ENTITIES,
    "events": schema.EVENTS,
    "summaries": schema.SUMMARIES,
}


def _frame(name: str) -> pl.DataFrame:
    if name not in FRAMES:
        raise HTTPException(404, f"unknown frame {name}")
    return schema.read_or_empty(schema.data_path(f"{name}.parquet"), FRAMES[name])


def _arrow(df: pl.DataFrame) -> Response:
    buf = io.BytesIO()
    df.write_ipc(buf)
    return Response(buf.getvalue(), media_type="application/vnd.apache.arrow.file")


@app.get("/api/frames/{name}")
def get_frame(name: str, page_id: str | None = None, letter_id: str | None = None) -> Response:
    df = _frame(name)
    if page_id and "page_id" in df.columns:
        df = df.filter(pl.col("page_id") == page_id)
    if letter_id and "letter_id" in df.columns:
        df = df.filter(pl.col("letter_id") == letter_id)
    return _arrow(df)


@app.get("/api/image/{page_id}")
def get_image(page_id: str, kind: str = "original") -> FileResponse:
    if kind == "processed":
        path = schema.data_path("processed") / f"{page_id}.jpg"
    else:
        pages = _frame("pages").filter(pl.col("page_id") == page_id)
        if pages.is_empty():
            raise HTTPException(404, "unknown page")
        path = Path(pages["source_path"][0])
    if not path.exists():
        raise HTTPException(404, "image missing")
    return FileResponse(path)


class Review(BaseModel):
    page_id: str
    text_final: str
    reviewed_by: str = "family"
    uncertain_spans: list[dict] = []


@app.post("/api/review")
def post_review(review: Review) -> dict:
    path = schema.data_path("letters.parquet")
    existing = schema.read_or_empty(path, schema.LETTERS)
    now = datetime.now()
    row = pl.DataFrame(
        [
            {
                "page_id": review.page_id,
                "text_final": review.text_final,
                "text_source": "reviewed",
                "uncertain_spans": review.uncertain_spans,
                "reviewed_by": review.reviewed_by,
                "reviewed_at": now,
                "updated_at": now,
            }
        ],
        schema=schema.LETTERS,
    )
    schema.write(schema.upsert(existing, row, ["page_id"]), path)
    return {"ok": True, "page_id": review.page_id}


class LetterMeta(BaseModel):
    letter_id: str
    date: str | None = None
    place: str | None = None
    recipient: str | None = None
    title: str | None = None
    notes: str | None = None


@app.post("/api/letter_meta")
def post_letter_meta(meta: LetterMeta) -> dict:
    path = schema.data_path("letter_meta.parquet")
    existing = schema.read_or_empty(path, schema.LETTER_META)
    row = (
        pl.DataFrame([meta.model_dump()])
        .with_columns(pl.col("date").str.to_date(strict=False))
        .cast(schema.LETTER_META)
    )
    schema.write(schema.upsert(existing, row, ["letter_id"]), path)
    return {"ok": True}


class PageAssign(BaseModel):
    page_id: str
    letter_id: str | None
    page_no: int | None


@app.post("/api/assign")
def post_assign(assign: PageAssign) -> dict:
    path = schema.data_path("pages.parquet")
    pages = _frame("pages")
    if assign.page_id not in set(pages["page_id"]):
        raise HTTPException(404, "unknown page")
    pages = pages.with_columns(
        pl.when(pl.col("page_id") == assign.page_id)
        .then(pl.lit(assign.letter_id))
        .otherwise(pl.col("letter_id"))
        .alias("letter_id"),
        pl.when(pl.col("page_id") == assign.page_id)
        .then(pl.lit(assign.page_no, pl.Int32))
        .otherwise(pl.col("page_no"))
        .alias("page_no"),
    )
    schema.write(pages, path)
    return {"ok": True}


UI_DIST = Path(__file__).resolve().parents[2] / "ui" / "dist"
if UI_DIST.exists():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
