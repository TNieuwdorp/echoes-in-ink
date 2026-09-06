#!/usr/bin/env bash
# Pre-download model weights so benchmarking does not wait on the network.
#   scripts/download_models.sh qwen38 gemma4 qwen36
# Requires `uv tool install huggingface_hub` (gives the `hf` command) and, for Gemma,
# an accepted licence on the Hub plus `hf auth login`.
set -euo pipefail
export HF_HUB_ENABLE_HF_TRANSFER="${HF_HUB_ENABLE_HF_TRANSFER:-1}"
declare -A REPOS=(
  [qwen38]="Qwen/Qwen3.8-27B"
  [qwen38-fp8]="Qwen/Qwen3.8-27B-FP8"
  [gemma4]="google/gemma-4-31B-it"
  [qwen36]="Qwen/Qwen3.6-35B-A3B"
  [qwen35-122b]="${QWEN35_122B_MODEL:-Qwen/Qwen3.5-122B-A10B-AWQ}"
)
for preset in "${@:-qwen38}"; do
  repo="${REPOS[$preset]:-}"
  [[ -z "$repo" ]] && { echo "unknown preset $preset" >&2; exit 1; }
  echo "==> $preset  ($repo)"
  hf download "$repo"
done
