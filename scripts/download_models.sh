#!/usr/bin/env bash
# Pre-download model weights so benchmarking does not wait on the network.
#   scripts/download_models.sh qwen38 gemma4 qwen36
# Requires `uv tool install huggingface_hub` (gives the `hf` command) and, for Gemma,
# an accepted licence on the Hub plus `hf auth login`.
# Sizes on disk: qwen38 ~27 GB, gemma4 ~29 GB, qwen36 ~33 GB, qwen38-bf16 ~54 GB, qwen35-122b ~62 GB.
set -euo pipefail
export HF_HUB_ENABLE_HF_TRANSFER="${HF_HUB_ENABLE_HF_TRANSFER:-1}"
declare -A REPOS=(
  [qwen38]="Qwen/Qwen3.8-27B-FP8"
  [qwen38-bf16]="Qwen/Qwen3.8-27B"
  [gemma4]="RedHatAI/gemma-4-31B-it-FP8-block"
  [qwen36]="Qwen/Qwen3.6-35B-A3B-FP8"
  [qwen35-122b]="${QWEN35_122B_MODEL:-Qwen/Qwen3.5-122B-A10B-GPTQ-Int4}"
)
for preset in "${@:-qwen38}"; do
  repo="${REPOS[$preset]:-}"
  [[ -z "$repo" ]] && { echo "unknown preset $preset" >&2; exit 1; }
  echo "==> $preset  ($repo)"
  hf download "$repo"
done
