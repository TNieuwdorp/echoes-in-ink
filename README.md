# Echoes in Ink

A project for building a custom [Claude Code output style](https://code.claude.com/docs/en/output-styles)
that writes the way the [Polars blog](https://pola.rs/posts/) writes.

The goal is a single Markdown file, `.claude/output-styles/polars-blog.md`, that makes Claude
draft blog posts, release notes, showcase write-ups, and training material in the Polars house voice:
technical, direct, code first, with real output and real numbers.

## How this works

Output styles change the system prompt, not what Claude knows. The style file has two parts:

1. YAML frontmatter with `name`, `description`, and `keep-coding-instructions`.
2. Free-form Markdown instructions that are appended to the system prompt.

Project-level styles live in `.claude/output-styles/` and are picked up when Claude Code starts
in this repository. Select the style with `/config` → **Output style**, or set it directly:

```json
{
  "outputStyle": "Polars Blog"
}
```

in `.claude/settings.local.json`. Restart Claude Code after editing the style file.

## Workflow

The style is derived from the actual posts, not from memory. The loop is:

```
fetch posts  →  analyze corpus  →  write down observations  →  refine the style  →  test it
```

### 1. Fetch the corpus

Downloads every post linked from `https://pola.rs/posts/` into `corpus/raw/<slug>.md`,
one Markdown file per post with a small frontmatter block (title, url, date).

```bash
uv run scripts/fetch_posts.py
```

`corpus/posts.txt` holds a seed list of known URLs. The script merges that list with whatever it
discovers on the index page, so you can add URLs by hand.

The raw posts are gitignored: they are Polars' content, and they are cheap to re-fetch.

### 2. Analyze the corpus

Uses Polars to compute per-post structure metrics: word counts, heading density, code-block
density, sentence length, pronoun usage, and how titles are phrased.

```bash
uv run scripts/analyze_corpus.py
```

Writes `corpus/stats.csv` and prints a summary. These numbers feed the "shape of a post"
section of the style.

### 3. Record observations

`corpus/notes/STYLE_NOTES.md` is the working document. Every claim in the style file should trace
back to an observation there, ideally with a quote and a post slug.

### 4. Refine the style

Edit `.claude/output-styles/polars-blog.md`. Keep it short: the system prompt is read on every
turn, and instructions that are not backed by the corpus are noise.

### 5. Test the style

`tests/prompts.md` lists prompts to run with the style active. Compare the output against a real
post of the same kind (release announcement, deep dive, case study, "Polars in Aggregate" recap).

## Layout

```
.claude/output-styles/polars-blog.md   the deliverable
corpus/posts.txt                       seed list of post URLs
corpus/raw/                            fetched posts (gitignored)
corpus/notes/STYLE_NOTES.md            observations that justify the style
corpus/stats.csv                       output of analyze_corpus.py (gitignored)
scripts/fetch_posts.py                 download posts as Markdown
scripts/analyze_corpus.py              Polars-based corpus statistics
tests/prompts.md                       prompts for evaluating the style
```

## Status

The current style file is a **first draft** written before the corpus was analyzed. It encodes
the post categories and conventions that are visible from the blog index and from well-known
posts. Treat every rule in it as a hypothesis until the corpus confirms it.
