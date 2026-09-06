"""Stage 6: copy the Parquet frames into the UI's public data folder with a manifest.

The Svelte app reads Parquet directly in the browser (parquet-wasm + Arrow JS), so the
family site is a static folder with no server.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import polars as pl

from . import schema

FRAMES = {
    "pages": schema.PAGES,
    "letters": schema.LETTERS,
    "letter_meta": schema.LETTER_META,
    "entities": schema.ENTITIES,
    "events": schema.EVENTS,
    "summaries": schema.SUMMARIES,
}


def export(out_dir: Path, include_images: bool = True) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"generated_at": datetime.now().isoformat(timespec="seconds"), "frames": {}}
    pages = schema.read_or_empty(schema.data_path("pages.parquet"), schema.PAGES)
    for name, sch in FRAMES.items():
        df = schema.read_or_empty(schema.data_path(f"{name}.parquet"), sch)
        if name == "pages":
            # the browser only needs relative image paths
            df = df.with_columns(
                pl.concat_str([pl.lit("images/"), pl.col("page_id"), pl.lit(".jpg")]).alias("image")
            )
        df.write_parquet(out_dir / f"{name}.parquet")
        manifest["frames"][name] = {"rows": df.height, "file": f"{name}.parquet"}
    if include_images:
        img_dir = out_dir / "images"
        img_dir.mkdir(exist_ok=True)
        processed = schema.data_path("processed")
        for pid, src in zip(pages["page_id"], pages["source_path"], strict=True):
            candidate = processed / f"{pid}.jpg"
            source = candidate if candidate.exists() else Path(src)
            if source.exists():
                shutil.copyfile(source, img_dir / f"{pid}.jpg")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest
