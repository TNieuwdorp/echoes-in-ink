"""Command line entry point: one subcommand per pipeline stage."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import typer
from rich.console import Console
from rich.table import Table

from . import schema

app = typer.Typer(
    help="Echoes in Ink: transcribe, enrich and explore handwritten letters.", no_args_is_help=True
)
console = Console()


def _page_ids(
    page: list[str] | None, letter: str | None, only_missing_in: Path | None = None
) -> list[str]:
    pages = schema.read_or_empty(schema.data_path("pages.parquet"), schema.PAGES)
    if page:
        return page
    if letter:
        pages = pages.filter(pl.col("letter_id") == letter)
    return pages["page_id"].to_list()


@app.command()
def ingest(
    directory: Path,
    letter: str | None = typer.Option(None, help="Force a letter_id for every image"),
) -> None:
    """Register images as pages (idempotent, keyed by content hash)."""
    from .ingest import ingest as run

    df = run(directory, letter_override=letter)
    console.print(f"{df.height} pages registered in {schema.data_path('pages.parquet')}")


@app.command()
def preprocess(
    page: list[str] | None = typer.Option(None, "--page", "-p"),
    letter: str | None = None,
    bands: int = 5,
    long_side: int = 2200,
    no_dewarp: bool = False,
    bleed: float = 0.6,
    force: bool = False,
) -> None:
    """Dewarp, enhance and cut bands for every registered page."""
    from .preprocess import PreprocessConfig, preprocess_page

    cfg = PreprocessConfig(
        long_side=long_side, dewarp=not no_dewarp, bands=bands, bleed_strength=bleed
    )
    pages = schema.read_or_empty(schema.data_path("pages.parquet"), schema.PAGES)
    ids = set(_page_ids(page, letter))
    out = schema.data_path("processed")
    n = 0
    for row in pages.filter(pl.col("page_id").is_in(list(ids))).iter_rows(named=True):
        if not force and (out / f"{row['page_id']}.jpg").exists():
            continue
        res = preprocess_page(Path(row["source_path"]), row["page_id"], out, cfg)
        n += 1
        console.print(
            f"{row['filename']} -> {res.page_path.name} ({len(res.band_paths)} bands, dewarped={res.quad is not None})"
        )
    console.print(f"{n} pages processed")


@app.command()
def transcribe(
    engine: str = typer.Option("local", help="local | gemini | claude"),
    model: str | None = None,
    page: list[str] | None = typer.Option(None, "--page", "-p"),
    letter: str | None = None,
    samples: int = 1,
    temperature: float = 0.6,
    with_bands: bool = False,
    few_shot: int = 2,
    thinking: bool = False,
) -> None:
    """Run pages through a vision model; every sample is stored."""
    from .engines import get_engine
    from .transcribe import transcribe_pages

    eng = get_engine(engine, model)
    ids = _page_ids(page, letter)
    df = transcribe_pages(
        eng,
        ids,
        samples=samples,
        temperature=temperature,
        with_bands=with_bands,
        few_shot=few_shot,
        thinking=thinking,
    )
    console.print(
        f"{df.height} lines written for {df['page_id'].n_unique() if df.height else 0} pages"
    )


@app.command()
def reconcile(
    page: list[str] | None = typer.Option(None, "--page", "-p"),
    letter: str | None = None,
    correct_with: str | None = typer.Option(
        None, help="Engine to resolve alternatives (e.g. local). Off by default."
    ),
    prefer: str = "local",
) -> None:
    """Vote across samples and engines; optionally let a text model resolve doubts."""
    from .reconcile import reconcile_pages

    corrector = None
    if correct_with:
        from .engines import get_engine

        corrector = get_engine(correct_with)
    df = reconcile_pages(_page_ids(page, letter), corrector, prefer)
    console.print(f"{df.height} pages reconciled -> {schema.data_path('letters.parquet')}")


@app.command()
def evaluate(detail: bool = False) -> None:
    """CER / WER / name recall of every system against the gold pages."""
    from .evaluate import run

    summary, per_page = run()
    if summary.is_empty():
        console.print("[yellow]nothing to evaluate yet: need transcriptions and gold pages[/]")
        return
    table = Table(title="Leaderboard (lower CER/WER is better)")
    for col in summary.columns:
        table.add_column(col)
    for row in summary.iter_rows():
        table.add_row(*[f"{v:.3f}" if isinstance(v, float) else str(v) for v in row])
    console.print(table)
    if detail:
        console.print(
            per_page.select("page_id", "engine", "model", "sample_no", "cer", "wer", "name_recall")
        )


@app.command()
def gold(
    promote: bool = typer.Option(
        False, help="Copy reviewed pages from letters.parquet into data/gold"
    ),
    seed: bool = typer.Option(
        False,
        help="Seed letters.parquet with the gold texts (text_source=gold) so the UI has content",
    ),
) -> None:
    """Show gold coverage, promote reviewed pages to gold, or seed letters from gold."""
    from datetime import datetime

    from .evaluate import load_gold

    pages = schema.read_or_empty(schema.data_path("pages.parquet"), schema.PAGES)
    gold_dir = schema.data_path("gold")
    if seed:
        g = load_gold(gold_dir, pages)
        now = datetime.now()
        rows = [
            {
                "page_id": r["page_id"],
                "text_final": "\n".join(
                    ln
                    for ln in r["gold_text"].splitlines()
                    if ln.strip() and not ln.lstrip().startswith("#")
                ),
                "text_source": "gold",
                "uncertain_spans": [],
                "reviewed_by": "gold",
                "reviewed_at": now,
                "updated_at": now,
            }
            for r in g.iter_rows(named=True)
        ]
        path = schema.data_path("letters.parquet")
        existing = schema.read_or_empty(path, schema.LETTERS)
        new = pl.DataFrame(rows, schema=schema.LETTERS) if rows else schema.empty(schema.LETTERS)
        schema.write(schema.upsert(existing, new, ["page_id"]), path)
        console.print(f"{new.height} gold pages seeded into letters.parquet")
    if promote:
        letters = schema.read_or_empty(schema.data_path("letters.parquet"), schema.LETTERS)
        reviewed = letters.filter(pl.col("text_source") == "reviewed").join(
            pages.select("page_id", "filename"), on="page_id"
        )
        for row in reviewed.iter_rows(named=True):
            (gold_dir / f"{Path(row['filename']).stem}.txt").write_text(
                row["text_final"] + "\n", encoding="utf-8"
            )
        console.print(f"{reviewed.height} reviewed pages written to {gold_dir}")
    g = load_gold(gold_dir, pages)
    console.print(f"{g.height} gold pages matched to {pages.height} registered pages")


@app.command()
def enrich(
    engine: str = "local", letter: list[str] | None = typer.Option(None, "--letter", "-l")
) -> None:
    """Extract people, places, events and summaries per letter."""
    from .engines import get_engine
    from .enrich import enrich as run

    run(get_engine(engine), letter)
    console.print("entities / events / summaries updated")


@app.command()
def export(out: Path = Path("ui/public/data"), no_images: bool = False) -> None:
    """Write Parquet frames (and page images) for the static family site."""
    from .export import export as run

    manifest = run(out, include_images=not no_images)
    console.print(manifest)


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Start the review backend (and the built UI if ui/dist exists)."""
    import uvicorn

    uvicorn.run("echoes.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    app()
