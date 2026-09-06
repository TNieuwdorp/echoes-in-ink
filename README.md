# Echoes in Ink

Transcribing, enriching and exploring the handwritten letters my grandfather, Wim
Nieuwdorp, sent home between 1945 and 1950: first from the Royal Netherlands Infantry
Depot under the British Liberation Army, later from the Dutch East Indies. He started
typing them up himself; this project finishes the job with local vision-language models,
Polars and a small Svelte site the family can browse.

Everything runs locally on a workstation with two RTX 6000 Ada cards. Cloud models are
an opt-in fallback, never the default.

## When you are back at the workstation

```bash
# 0. one-time
uv sync --extra dev                      # Python side
(cd ui && npm install)                   # UI side
uv tool install vllm                     # model server (needs vLLM >= 0.21 for Qwen3.8 and Gemma 4)
uv tool install huggingface_hub          # gives the `hf` command; `hf auth login` for Gemma
just download qwen38                     # FP8, ~27 GB; add gemma4 qwen36 later

# 1. serve a model (terminal A) and benchmark it on the sample pages (terminal B)
just serve qwen38                        # GPU 0, port 8000; GPU=1 PORT=8001 just serve gemma4 runs beside it
just bench qwen38                        # prints the CER/WER leaderboard against data/gold

# 2. photograph or scan ten letters (see "Capturing the letters"), then
just ingest ~/scans/batch1               # files named <letter>_p<n>.jpg, e.g. 1945-03-15_p1.jpg
just transcribe qwen38                   # greedy + 2 sampled passes with zoom bands, then voting
just review                              # http://localhost:5173 : correct pages, they become gold
uv run echoes gold --promote             # reviewed pages -> data/gold, re-run `just bench`

# 3. compare candidates by serving another preset and re-running `just bench <preset>`
```

Presets in `scripts/serve_vllm.sh`, sized for one 48 GiB RTX 6000 Ada each (weights, then
what is left for KV cache at `--max-model-len 32768`):

| Preset | Checkpoint | Weights | GPUs | KV cache left |
|---|---|---|---|---|
| `qwen38` (default) | `Qwen/Qwen3.8-27B-FP8` | ~27 GiB | 1 | ~14 GiB, 7 sequences of 32k |
| `gemma4` | `RedHatAI/gemma-4-31B-it-FP8-block` | ~29 GiB | 1 | ~12 GiB |
| `qwen36` | `Qwen/Qwen3.6-35B-A3B-FP8` (fast sampler) | ~33 GiB | 1 | ~8 GiB, 13 sequences |
| `qwen38-bf16` | `Qwen/Qwen3.8-27B` (one-off accuracy check) | 25 GiB per card | 2 | ~16 GiB per card |
| `qwen35-122b` | `Qwen/Qwen3.5-122B-A10B-GPTQ-Int4` | 31 GiB per card | 2 | ~10 GiB per card |

A bf16 27B is ~50 GiB of weights and does not fit one card, hence FP8 by default; Ada has
FP8 tensor cores, and Qwen's own FP8 build benchmarks the same as bf16. The Qwen models are
hybrids where only a quarter of the layers keep a KV cache (64 KiB per token for the 27B),
so 32k of context costs about 2 GiB per sequence. `GPU=`, `PORT=`, `MAX_LEN=`, `MAX_IMAGES=`
and `DRY_RUN=1` override the script. The pipeline reads `ECHOES_LOCAL_BASE_URL` and
`ECHOES_LOCAL_MODEL` (the served name, e.g. `qwen38`).

If `just` is not installed, every recipe in `justfile` is one or two plain commands.

## Pipeline

```
photos ─► echoes ingest ─► echoes preprocess ─► echoes transcribe ─► echoes reconcile ─► echoes enrich ─► echoes export
          pages.parquet    data/processed/       transcriptions.parquet  letters.parquet     entities/events/   ui/public/data
                                                                                             summaries.parquet
```

- **ingest**: content-hashed `page_id`, EXIF, letter and page number from the filename.
- **preprocess**: find the sheet, perspective-warp it, divide out the background (kills
  bleed-through from the reverse side), levels stretch, resize to 2200 px, cut 5
  overlapping bands. Bands are sent with the full page so the model sees each line large.
- **transcribe**: system prompt in `prompts/transcribe.md` (Dutch, period, names list from
  `data/names.txt`), two few-shot gold pages as prior turns, JSON lines with confidence.
  Every sample of every model is stored, keyed by prompt version.
- **reconcile**: align lines across samples, vote per word, keep alternatives; optionally
  a text pass (`--correct-with local`) resolves them with Dutch knowledge. Reviewed pages
  are never overwritten.
- **evaluate**: CER, WER and name recall per system against `data/gold`.
- **enrich**: people, places, events, summaries per letter; fuzzy entity clustering.
- **export**: Parquet + images into `ui/public/data`; the site reads Parquet in the browser.

Engines: `local` (vLLM, default), `gemini` (best value cloud, needs `GEMINI_API_KEY`),
`claude` (top performer). `claude` needs no API key: it runs `claude -p` through the logged-in
Claude Code CLI on your subscription (only the `Read` tool enabled, images staged in a scratch
directory, structured JSON output); with `ANTHROPIC_API_KEY` set it uses the SDK instead, and
`claude-cli` / `claude-api` force either. `just ceiling` runs the gold pages through Claude to
measure how far the local model is from the frontier.

Working on this repo with a Claude agent: `CLAUDE.md` holds the conventions and
`docs/agent-brief.md` the experiment plan it should follow on the workstation. Extra feature
ideas live in `docs/ideas.md`.

## UI

`ui/` is a Vite + Svelte 5 app with d3, Apache Arrow and parquet-wasm. One codebase, two
modes: with `echoes serve` running it is the review tool (edit and save transcriptions,
Arrow IPC over `/api`); `npm run build` after `echoes export` produces a static folder that
reads the Parquet files directly in the browser, so the family site needs no server.
Views: timeline (zoom and drag; letters, extracted events, historical anchors), letter
reader (photo beside text, uncertain words highlighted with alternatives), search, people
and places.

## Capturing the letters

Flatbed scanner (preferred for the whole corpus): 400 dpi, 24-bit colour, PNG or TIFF,
every auto-enhance option off, letter out of the sleeve, matte black card behind the page.

Pixel 8 Pro (for experiments and pages that cannot be scanned):
- take the letter out of the plastic sleeve; this matters more than any setting
- Camera > Settings > Pro: resolution Full (50 MP), RAW+JPEG on; main 1x lens only
- Pro controls: tap to focus on the text, ISO fixed at 50 to 100, fixed white balance,
  Night Sight off, no flash
- light from a window or two lamps at 45 degrees left and right; no overhead light
- phone parallel to the page on a stand, grid and level on, page filling about 80% of
  the frame, matte black card underneath
- 3-second timer or volume button; never tap the screen to shoot
- name files `<letter>_p<n>.jpg`, e.g. `1945-03-15_p1.jpg`, `1945-03-15_p2.jpg`, or
  photograph an index card with the letter id before each letter and rename afterwards

## Gold data and evaluation

`data/gold/*.txt` holds verified transcriptions matched to images by filename stem.
The two `1945-03-15_*` files were produced by Claude from the sample photos and are
provisional. Pages listed in `data/gold/holdout.txt` are never used as few-shot examples.
Correcting model output in the review UI is much faster than typing from scratch; aim
for 8 to 10 gold pages across years and paper conditions before trusting the leaderboard.

## Layout

```
src/echoes/        pipeline (ingest, preprocess, transcribe, reconcile, evaluate, enrich, export, server, cli)
src/echoes/engines openai_compat (vLLM, Gemini), anthropic_engine
prompts/           transcribe.md, correct.md, extract.md (hash-versioned)
scripts/           serve_vllm.sh, download_models.sh
data/              gold/, names.txt; raw/, processed/ and *.parquet are git-ignored
ui/                Svelte app (review tool and family site)
tests/             pytest on the three sample photos in tests/fixtures
```
