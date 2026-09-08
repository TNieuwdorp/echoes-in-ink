# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx", "beautifulsoup4", "markdownify"]
# ///
"""Download Polars blog posts as Markdown into corpus/raw/.

Discovers posts from https://pola.rs/posts/ and merges them with corpus/posts.txt.
Each post is written to corpus/raw/<slug>.md with a frontmatter block.

    uv run scripts/fetch_posts.py            # fetch everything not yet downloaded
    uv run scripts/fetch_posts.py --force    # re-fetch everything
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify

ROOT = Path(__file__).resolve().parent.parent
INDEX_URL = "https://pola.rs/posts/"
SEED_FILE = ROOT / "corpus" / "posts.txt"
RAW_DIR = ROOT / "corpus" / "raw"
POST_RE = re.compile(r"^/posts/[^/]+/?$")


def read_seed_urls(path: Path) -> list[str]:
    if not path.exists():
        return []
    urls = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line.rstrip("/") + "/")
    return urls


def discover_urls(html: str, base: str = INDEX_URL) -> list[str]:
    """Return post URLs linked from the blog index, deduplicated and in page order."""
    soup = BeautifulSoup(html, "html.parser")
    seen: dict[str, None] = {}
    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"])
        path = urlparse(href).path
        if POST_RE.match(path) and path.rstrip("/") != "/posts":
            seen[href.rstrip("/") + "/"] = None
    return list(seen)


def slug_of(url: str) -> str:
    return urlparse(url).path.rstrip("/").split("/")[-1]


def extract_post(html: str, url: str) -> tuple[dict[str, str], str]:
    """Return (metadata, markdown body) for a post page."""
    soup = BeautifulSoup(html, "html.parser")
    meta: dict[str, str] = {"url": url}

    if soup.title and soup.title.string:
        meta["title"] = re.sub(r"^\s*Polars\s*[—-]\s*", "", soup.title.string).strip()
    if (h1 := soup.find("h1")) is not None:
        meta["title"] = h1.get_text(strip=True) or meta.get("title", "")
    if (t := soup.find("time")) is not None:
        meta["date"] = t.get("datetime") or t.get_text(strip=True)
    if (og := soup.find("meta", property="article:published_time")) is not None:
        meta.setdefault("date", og.get("content", ""))

    body = soup.find("article") or soup.find("main") or soup.body or soup
    for tag in body.find_all(["nav", "header", "footer", "script", "style"]):
        tag.decompose()
    markdown = markdownify(str(body), heading_style="ATX", code_language="python")
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip() + "\n"
    return meta, markdown


def write_post(meta: dict[str, str], body: str, dest: Path) -> None:
    front = "\n".join(f'{k}: "{v}"' for k, v in meta.items() if v)
    dest.write_text(f"---\n{front}\n---\n\n{body}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-fetch posts already on disk")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    urls = read_seed_urls(SEED_FILE)

    with httpx.Client(follow_redirects=True, timeout=30, headers={"User-Agent": "echoes-in-ink/0.1"}) as client:
        try:
            index = client.get(INDEX_URL)
            index.raise_for_status()
            for url in discover_urls(index.text):
                if url not in urls:
                    urls.append(url)
        except httpx.HTTPError as exc:
            print(f"warning: could not read {INDEX_URL}: {exc}", file=sys.stderr)

        fetched = skipped = failed = 0
        for url in urls:
            dest = RAW_DIR / f"{slug_of(url)}.md"
            if dest.exists() and not args.force:
                skipped += 1
                continue
            try:
                resp = client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                print(f"failed: {url}: {exc}", file=sys.stderr)
                failed += 1
                continue
            meta, body = extract_post(resp.text, url)
            write_post(meta, body, dest)
            fetched += 1
            print(f"fetched: {dest.relative_to(ROOT)}")

    print(f"\n{fetched} fetched, {skipped} already present, {failed} failed, {len(urls)} total")
    return 1 if failed and not fetched else 0


if __name__ == "__main__":
    raise SystemExit(main())
