# /// script
# requires-python = ">=3.11"
# dependencies = ["polars>=1.0"]
# ///
"""Compute structure metrics for the fetched Polars blog posts.

Reads corpus/raw/*.md, writes corpus/stats.csv, prints a summary. The numbers describe the
*shape* of a post (length, heading density, code density, sentence length, voice) so the output
style can encode what the blog actually does rather than what we remember it doing.

    uv run scripts/analyze_corpus.py
"""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "corpus" / "raw"
OUT_FILE = ROOT / "corpus" / "stats.csv"

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
CODE_BLOCK_RE = re.compile(r"```.*?```", re.S)


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"')
    return meta, text[m.end():]


def load_posts(raw_dir: Path) -> pl.DataFrame:
    rows = []
    for path in sorted(raw_dir.glob("*.md")):
        meta, body = split_frontmatter(path.read_text())
        code_blocks = CODE_BLOCK_RE.findall(body)
        prose = CODE_BLOCK_RE.sub("", body)
        rows.append(
            {
                "slug": path.stem,
                "title": meta.get("title", ""),
                "date": meta.get("date", ""),
                "prose": prose,
                "n_code_blocks": len(code_blocks),
                "code_lines": sum(b.count("\n") - 1 for b in code_blocks),
                "n_output_blocks": sum("shape:" in b for b in code_blocks),
            }
        )
    return pl.DataFrame(rows)


def add_metrics(posts: pl.DataFrame) -> pl.DataFrame:
    prose = pl.col("prose")
    return (
        posts.with_columns(
            words=prose.str.count_matches(r"\S+"),
            sentences=prose.str.count_matches(r"[.!?](\s|$)"),
            h2=prose.str.count_matches(r"(?m)^## "),
            h3=prose.str.count_matches(r"(?m)^### "),
            bullets=prose.str.count_matches(r"(?m)^\s*[-*] "),
            tables=prose.str.count_matches(r"(?m)^\|"),
            links=prose.str.count_matches(r"\]\(http"),
            questions=prose.str.count_matches(r"\?"),
            exclamations=prose.str.count_matches(r"!"),
            we=prose.str.count_matches(r"(?i)\bwe\b"),
            i=prose.str.count_matches(r"\bI\b"),
            you=prose.str.count_matches(r"(?i)\byou\b"),
            title_words=pl.col("title").str.count_matches(r"\S+"),
            # words starting with a capital, excluding the first word and "Polars": 0 means sentence case
            title_cap_words=(
                pl.col("title").str.count_matches(r"\b[A-Z][A-Za-z]*")
                - pl.col("title").str.count_matches(r"\bPolars\b")
                - 1
            ).clip(lower_bound=0),
        )
        .with_columns(
            words_per_sentence=(pl.col("words") / pl.col("sentences").clip(lower_bound=1)).round(1),
            words_per_h2=(pl.col("words") / pl.col("h2").clip(lower_bound=1)).round(0),
            code_ratio=(pl.col("code_lines") / (pl.col("code_lines") + pl.col("words") / 10)).round(2),
            we_per_kw=(pl.col("we") / pl.col("words") * 1000).round(1),
            you_per_kw=(pl.col("you") / pl.col("words") * 1000).round(1),
        )
        .drop("prose")
    )


def categorize(stats: pl.DataFrame) -> pl.DataFrame:
    slug = pl.col("slug")
    return stats.with_columns(
        category=pl.when(slug.str.contains("aggreg"))
        .then(pl.lit("recap"))
        .when(slug.str.contains(r"announcing|^polars-\d"))
        .then(pl.lit("release"))
        .when(slug.str.contains("case"))
        .then(pl.lit("case-study"))
        .when(slug.str.contains("cloud"))
        .then(pl.lit("cloud"))
        .when(slug.str.contains("company|series"))
        .then(pl.lit("company"))
        .otherwise(pl.lit("deep-dive"))
    )


def main() -> int:
    posts = load_posts(RAW_DIR)
    if posts.is_empty():
        print(f"no posts in {RAW_DIR}. Run: uv run scripts/fetch_posts.py")
        return 1

    stats = categorize(add_metrics(posts))
    stats.write_csv(OUT_FILE)

    with pl.Config(tbl_rows=-1, tbl_cols=-1, tbl_width_chars=160, fmt_str_lengths=40):
        print("Per post\n")
        print(
            stats.select(
                "slug", "category", "words", "h2", "n_code_blocks", "n_output_blocks",
                "words_per_sentence", "code_ratio", "we_per_kw", "you_per_kw", "questions", "exclamations",
            )
        )
        print("\nPer category (median)\n")
        print(
            stats.group_by("category")
            .agg(
                pl.len().alias("posts"),
                pl.col("words", "h2", "n_code_blocks", "words_per_sentence", "code_ratio", "we_per_kw", "you_per_kw")
                .median()
                .round(1),
            )
            .sort("posts", descending=True)
        )
        print("\nTitles\n")
        print(stats.select("category", "title", "title_words", "title_cap_words").sort("category"))

    print(f"\nwrote {OUT_FILE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
