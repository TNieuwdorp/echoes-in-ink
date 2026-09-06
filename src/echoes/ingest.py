"""Stage 1: register images as pages.

``page_id`` is the first 16 hex chars of the sha256 of the file bytes, so a page keeps
its identity when files are moved or renamed. Letter grouping comes from the filename
convention ``<letter_id>_p<page_no>.<ext>`` (e.g. ``1945-03-15_p1.jpg`` or
``L042_p2.jpg``); anything else is ingested with a null letter_id and grouped later in
the review UI.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

import polars as pl
from PIL import ExifTags, Image

from . import schema

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".heic"}
FILENAME_RE = re.compile(r"^(?P<letter>.+?)_p(?P<page>\d+)(?:_.*)?$", re.IGNORECASE)


def page_id_for(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def parse_filename(stem: str) -> tuple[str | None, int | None]:
    m = FILENAME_RE.match(stem)
    if not m:
        return None, None
    return m.group("letter"), int(m.group("page"))


def read_exif(img: Image.Image) -> tuple[datetime | None, str | None]:
    exif = img.getexif()
    if not exif:
        return None, None
    tags = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
    captured = None
    raw = tags.get("DateTimeOriginal") or tags.get("DateTime")
    if isinstance(raw, str):
        try:
            captured = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            captured = None
    make = tags.get("Make")
    model = tags.get("Model")
    camera = " ".join(str(x).strip() for x in (make, model) if x) or None
    return captured, camera


def iter_images(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES)


def ingest_dir(root: Path, letter_override: str | None = None) -> pl.DataFrame:
    rows = []
    now = datetime.now()
    for path in iter_images(root):
        with Image.open(path) as img:
            width, height = img.size
            captured, camera = read_exif(img)
        letter_id, page_no = parse_filename(path.stem)
        if letter_override:
            letter_id = letter_override
        rows.append(
            {
                "page_id": page_id_for(path),
                "source_path": str(path.resolve()),
                "filename": path.name,
                "letter_id": letter_id,
                "page_no": page_no,
                "width": width,
                "height": height,
                "captured_at": captured,
                "camera": camera,
                "ingested_at": now,
            }
        )
    if not rows:
        return schema.empty(schema.PAGES)
    return pl.DataFrame(rows, schema=schema.PAGES)


def ingest(
    root: Path, pages_path: Path | None = None, letter_override: str | None = None
) -> pl.DataFrame:
    pages_path = pages_path or schema.data_path("pages.parquet")
    new = ingest_dir(root, letter_override)
    existing = schema.read_or_empty(pages_path, schema.PAGES)
    merged = schema.upsert(existing, new, ["page_id"]).sort(["letter_id", "page_no", "captured_at"])
    schema.write(merged, pages_path)
    return merged
