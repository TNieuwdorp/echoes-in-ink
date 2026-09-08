# Evaluation prompts

Run each prompt with the **Polars Blog** output style active and compare the result against the
reference post. Note what the style got right, what it got wrong, and update
`.claude/output-styles/polars-blog.md` and `corpus/notes/STYLE_NOTES.md`.

## Release announcement

> Write the announcement post for Polars 1.43. Headline features: `pl.list()` for packing
> columns into a list column, `ewm_sum` / `ewm_sum_by`, and O(n) rolling `min_by` / `max_by`.

Reference: `corpus/raw/polars-1-43.md`

## Deep dive

> Write a post explaining how Polars chooses between the in-memory engine and the streaming
> engine, and what that means for users calling `.collect()`.

Reference: `corpus/raw/understanding-polars-data-types.md` (for tone and structure)

## Recap

> Write a "Polars in Aggregate" post covering releases 1.41 through 1.44.

Reference: `corpus/raw/polars-in-aggregate-apr26.md`

## Training material

> Write a 20 minute workshop section on `group_by` with the lazy API for people coming from pandas.

No reference post. Check that the voice and code conventions carry over to non-blog formats.

## Negative test

> Write a fun, upbeat LinkedIn post about how amazing Polars is!

The style should push back on tone: no exclamation marks, no hype, numbers with context.

## Checklist

- [ ] Title is a plain statement in sentence case
- [ ] First paragraph states what and why, no "in this post we will"
- [ ] Every code example has `import polars as pl` once and printed output with `shape:`
- [ ] Performance claims have dataset, size, hardware, version
- [ ] No emoji, no exclamation marks, no rhetorical questions
- [ ] Ends with an action: upgrade command, changelog link, or issue tracker
