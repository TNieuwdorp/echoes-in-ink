# Style notes

Observations about how the Polars blog is written. Each note should name the post(s) it comes
from so the style file can be audited. Fill this in after running the fetch and analyze scripts.

## Post categories seen on the index

| Category | Example slugs | Notes |
| :-- | :-- | :-- |
| Release announcement | `announcing-polars-1`, `polars-1-41`, `polars-1-43` | one H2 per headline feature, code + output per feature |
| "Polars in Aggregate" recap | `polars_in_aggregrate-0.20`, `polars-in-aggregate-dec25`, `polars-in-aggregate-apr26` | period recap across several releases |
| Technical deep dive | `understanding-polars-data-types`, `lightweight_plotting` | explains a concept or subsystem, heavier on prose |
| Product / Cloud | `polars-cloud-what-we-are-building`, `polars-cloud-launch` | architecture, motivation, what ships |
| Case study | `case-citizens` | customer story, problem → approach → result |
| Company | `company-announcement`, `series_a` | funding, hiring, direction |

## Title conventions

- TODO: confirm. Index titles are plain declaratives: "Announcing Polars 1.43", "Understanding Polars data types", "Polars has a new lightweight plotting backend". Sentence case, no clickbait, no question titles.

## Opening paragraph

- TODO: how many sentences, does it state the "what" and the "why" up front, does it link to the changelog.

## Body structure

- TODO: H2 per feature or concept? Are H3s used? Where do code blocks sit relative to explanation?
- TODO: is printed DataFrame output (the `shape: (n, m)` table) shown after code?

## Code conventions

- TODO: lazy vs eager in examples, `pl.col` vs string column names, one method per line in chains, `import polars as pl` shown or assumed.

## Voice

- TODO: "we" vs "I" vs "you". How often does the post address the reader directly?
- TODO: how are performance claims phrased? Numbers with hardware and dataset named, or relative ("2x faster")?

## Closing

- TODO: does every post end with a call to action (upgrade command, Discord, GitHub issues, Cloud waitlist)?

## Things the blog does NOT do

- TODO: capture anti-patterns so the style can forbid them (emoji, rhetorical questions, "in this blog post we will...", etc.).
