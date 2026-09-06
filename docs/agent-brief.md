# Brief for the workstation agent

## Mission

Get the best possible Dutch transcription of Wim Nieuwdorp's letters (1945–1950) out of the
local hardware, prove it with numbers on the gold set, and leave the pipeline ready for the
full corpus. Every decision comes from the leaderboard (`uv run echoes evaluate --detail`),
not from eyeballing a page.

Owner: Thijs. Repo `echoes-in-ink`, branch `claude/grandpa-letters-ocr-5l79x0`. Read
`README.md` and `CLAUDE.md` first, then `prompts/`, `data/gold/README.md` and
`scripts/serve_vllm.sh`. The hard rules in `CLAUDE.md` apply throughout.

## Hardware and memory budget

Two RTX 6000 Ada, 48 GiB each, FP8 tensor cores (SM89). vLLM takes
`--gpu-memory-utilization 0.92` of a card (about 44 GiB), keeps the weights and an activation
workspace (about 3 GiB with images), and gives the rest to KV cache.

Our request is roughly 17k tokens (system prompt and names, two few-shot pages as images
with their gold text, the target page, five zoom bands) plus 1.5k output, so
`--max-model-len 32768` with 4 to 8 requests in flight.

| Preset | Checkpoint | Weights | Cards | KV left | 32k sequences |
|---|---|---|---|---|---|
| `qwen38` (default) | `Qwen/Qwen3.8-27B-FP8` | ~27 GiB | 1 | ~14 GiB | 7 |
| `gemma4` | `RedHatAI/gemma-4-31B-it-FP8-block` | ~29 GiB | 1 | ~12 GiB | 6 |
| `qwen36` | `Qwen/Qwen3.6-35B-A3B-FP8` | ~33 GiB | 1 | ~8 GiB | 13 |
| `qwen38-bf16` | `Qwen/Qwen3.8-27B`, TP 2 | 25 GiB per card | 2 | ~16 GiB per card | 16 |
| `qwen35-122b` | `Qwen/Qwen3.5-122B-A10B-GPTQ-Int4`, TP 2 | 31 GiB per card | 2 | ~10 GiB per card | 26 |

Why the KV numbers are small: the Qwen models are Gated DeltaNet hybrids where only one
layer in four keeps a KV cache (Qwen3.8-27B: 16 of 64 layers, 4 KV heads, head_dim 256, so
64 KiB per token and 2 GiB per 32k sequence; the 35B-A3B: 20 KiB per token). Gemma 4 31B
has 10 global layers (4 heads, head_dim 512, shared K and V) and 50 local layers with a
1,024-token window, about 2 GiB per 32k sequence as well, but only on vLLM 0.21 or newer,
where the local layers stopped being allocated at full length.

Rules that follow from this:

- A bf16 27B is ~50 GiB of weights and does not fit one card. Single-card presets are FP8.
  `qwen38-bf16` exists only to check once that FP8 does not change CER.
- Int4 is not used for the 27B (FP8 already leaves 14 GiB; int4 costs accuracy on names).
  It is the only way to fit the 122B on two cards.
- `--max-num-seqs 8` on every preset: the Qwen hybrids pre-allocate recurrent state per slot.
- Two single-card presets run side by side: `GPU=0 PORT=8000 just serve qwen38` and
  `GPU=1 PORT=8001 just serve gemma4`; `just bench gemma4 8001` points the pipeline at the
  second one.
- If vLLM's start-up log reports much less KV cache than the table, lower `MAX_IMAGES` from
  10 to 8 first (it bounds the vision workspace), then `MAX_LEN` to 24576. Never raise
  `--gpu-memory-utilization` above 0.95.

## Phase 0: environment (first 30 minutes)

1. `nvidia-smi`: two RTX 6000 Ada, 48 GiB each; note the driver version.
2. `just setup`, then `just test`. All tests must pass before anything else.
3. `uv tool install vllm` (or `uv tool upgrade vllm`) and `uv tool install huggingface_hub`.
   Record the vLLM version in the first report; it must be 0.21 or newer.
4. `just download qwen38` (FP8, about 27 GB on disk; check free space first).
5. `just serve qwen38` in a second terminal. Wait for "Application startup complete" and
   read the line that reports the KV cache size: expect roughly 14 GiB, or about 200k tokens.
   Smoke test with `curl localhost:8000/v1/models` and one chat call with a fixture image.
6. `just bench qwen38`. This is the baseline. Write `docs/experiments/00-baseline.md` from
   the template in `docs/experiments/README.md` before changing anything.

Stop and report to Thijs, without further experiments, if CER on both pages is above 0.40
(the model probably never saw the image, or JSON parsing failed), if vLLM cannot load the
model, or if the tests fail.

## Phase 1: preprocessing ablation (same model, one variable at a time)

Use `echoes preprocess` with `PreprocessConfig` overrides, transcribe the two fixture pages
and the binder photo, evaluate. In order of expected impact:

1. Input: raw photo, dewarped, dewarped plus bleed suppression, plus levels (the default).
2. Long side: 1600, 2200 (default), 3000 px. Watch tokens per image and KV use.
3. Bands: page only vs `--with-bands`; band count 4 and 6; overlap 0.12 and 0.25.
4. Unsharp 0.0, 0.4 (default), 0.8.

Keep the winner as the new default in `src/echoes/preprocess.py`, numbers in the commit message.

## Phase 2: prompt and decoding ablation

1. Few-shot 0, 1, 2 gold pages. `data/gold/holdout.txt` keeps pages out of few-shot; never
   evaluate on a page that was used as an example.
2. Names list on and off.
3. Thinking off (default for transcription) vs on. Expect slower and not better; confirm.
4. Samples 1, 3, 5 with voting in `echoes reconcile`, and the correction pass
   `--correct-with local` on and off. Report CER before and after correction separately.
   Correction that lowers CER but hurts name recall is a regression.
5. Temperature for the sampled passes: 0.4, 0.6, 0.8.

## Phase 3: model ladder

Run the bench with the best Phase 1 and 2 settings for `qwen38`, `gemma4`, `qwen36`, then
`qwen35-122b` only if the 27B plateaus. For each record CER, WER, name recall, seconds per
page and the KV cache size vLLM reported. Run `qwen38-bf16` once against `qwen38` on the same
pages: if CER differs by more than 0.5 points report it, otherwise never use bf16 again.

Then the ensemble: best model greedy, fast model sampled, second model as another vote,
reconciled by `echoes reconcile`. Does the vote beat the best single model?

## Phase 4: ceiling (only on Thijs's explicit go)

`just ceiling` runs the gold pages through Claude Opus 5 via the Claude Code CLI on Thijs's
subscription. Check `claude auth status` first; for unattended runs Thijs can export
`CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`. Do not use `--bare` anywhere: it ignores
the subscription login. Pages run one at a time. If `GEMINI_API_KEY` is present, also run
`--engine gemini`. Report the gap between the best local result and the ceiling. Under 2 CER
points: local is enough and the cloud fallback stays off. Otherwise propose the disagreement
threshold for sending only hard pages.

## Phase 5: real letters

When Thijs has scanned or photographed the first ten letters into `data/raw/<batch>/`:

1. `just ingest data/raw/<batch>`, then `just transcribe`.
2. Ask Thijs to correct the pages in `just review` and promote them with
   `uv run echoes gold --promote`. Put two whole letters from different years into
   `holdout.txt`.
3. Re-run Phases 1 to 3 on the larger gold set. Expect rankings to change: the sample pages
   are 1945 depot letters, the Indies letters may differ in paper and pen.
4. Refresh the names list from reviewed pages (`uv run echoes gold --seed`).
5. `uv run echoes enrich` on reviewed letters, then `just site`; check the timeline and the
   entity clustering by eye. Report false merges (two people clustered as one) and misses.

## Things that go wrong, and what they look like

- Fluent but wrong: low CER on common words while names are invented. Read name recall
  next to CER, always.
- Truncated output: thinking left on or `max_tokens` too low. `parse_lines_json` falls back
  to plain lines; check the raw reply.
- Gold leakage: a few-shot page also in the evaluation set. `few_shot_examples` excludes the
  page itself and the holdout; re-check when gold grows.
- Bleed-through read as text: extra short lines. The preprocessing ablation shows it.
- Line merges: two short lines joined. CER barely moves but alignment in `reconcile`
  degrades; inspect `align_lines` output.
- Too little KV cache or out of memory: the model must be an FP8 or int4 checkpoint on a
  48 GiB card. Lower `MAX_IMAGES`, then `MAX_LEN`; keep `--max-num-seqs 8`. Note the fix.
- Wrong `ECHOES_LOCAL_MODEL`: rows get an unexpected `model` value and the leaderboard splits
  them. Check the served name on `/v1/models`.
- Claude CLI returns `is_error` or no JSON: usually a usage limit or an expired login. Wait or
  re-login; do not loop on retries.

## Reporting

One file per experiment in `docs/experiments/` from the template, plus a running
`docs/experiments/LEADERBOARD.md` with the best configuration per model. Commit each report.

Time budget: about 30 minutes of GPU time per experiment. When Thijs is back at the machine,
give a five-line summary: best configuration, its numbers, the one thing that helped most,
the one thing that surprised you, and what needs a human next.
