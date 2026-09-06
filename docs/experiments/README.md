# Experiment reports

One file per experiment, `NN-short-name.md`, numbered in the order they were run. Keep
`LEADERBOARD.md` in this directory current: the best configuration per model with its
numbers, updated whenever a report changes the ranking.

Template:

```markdown
# NN. Short name

**Question.** One sentence: what decision does this experiment inform?

**Setup.**
- Model / preset and vLLM version:
- Prompt file and version hash:
- Preprocess config (only what differs from the defaults in `preprocess.py`):
- Samples, temperature, few-shot k, thinking, bands:
- Gold pages evaluated (and which were held out):

**Result.** Paste the table from `uv run echoes evaluate --detail` unchanged.

**Reading.** One paragraph on the worst lines: what kind of error dominates (names,
line merges, bleed-through, hallucinated fluent Dutch), and whether name recall moved
with CER.

**Decision.** What changes in the defaults, or nothing, and why.

**Next question.** The single most useful thing to test after this.
```

Numbers are only comparable when the gold set is the same. When gold grows, re-run the
current best configuration first so the leaderboard has a fresh baseline.
