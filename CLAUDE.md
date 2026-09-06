# Echoes in Ink

Transcription, enrichment and presentation of Wim Nieuwdorp's handwritten Dutch letters
(1945–1950). Owner: Thijs. Read `README.md` first; the experiment plan for an agent on the
workstation is `docs/agent-brief.md`; feature ideas are in `docs/ideas.md`.

## Conventions

- Python 3.11+, `uv`. Run things with `uv run echoes ...` or the `justfile` recipes.
  `just test` runs pytest and ruff; both must be clean before a commit.
- Polars everywhere, Parquet as the only data format. Schemas live in `src/echoes/schema.py`;
  add columns there, never ad hoc. Frames are upserted by key, never rewritten blindly.
- Every pipeline stage is an idempotent CLI subcommand keyed by `page_id`.
- Prompts are versioned by content hash (`prompts/*.md`). For an experiment, copy the prompt
  to a new file rather than editing in place, so old runs stay reproducible.
- The UI is Svelte 5 with runes, TypeScript, d3, Apache Arrow and parquet-wasm. No component
  frameworks, no Streamlit.

## Hard rules

- Never modify, move or delete anything under `data/raw/`.
- Never call a cloud engine (`--engine gemini|claude|claude-cli|claude-api`) unless Thijs has
  asked for it in the current session. Claude runs on Thijs's subscription through the
  Claude Code CLI and shares his usage limits; keep it to gold pages.
- Never delete rows from `data/transcriptions.parquet`; every model output is evidence.
- Only change `data/gold/*.txt` through `echoes gold --promote` after a human review.
  The two `1945-03-15_*` gold files are provisional machine transcriptions until Thijs
  confirms them.
- One GPU job at a time per card. Check `nvidia-smi` and stop your own vLLM before starting
  another on the same GPU. Each RTX 6000 Ada has 48 GiB: single-card presets are FP8, a bf16
  27B does not fit one card.
- Commit after each experiment with its report in `docs/experiments/`. No pull requests
  unless asked. No model identifiers or session links in committed files.
