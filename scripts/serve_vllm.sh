#!/usr/bin/env bash
# Start a local vLLM server for one of the benchmark candidates.
#
# Each RTX 6000 Ada has 48 GiB. A bf16 27B model is ~50 GiB of weights and does not fit
# one card, so every single-card preset is an FP8 checkpoint (Ada has FP8 tensor cores)
# and leaves 8-14 GiB of KV cache; only the bf16 check and the 122B use both cards.
#
#   scripts/serve_vllm.sh qwen38            # Qwen3.8-27B-FP8, one GPU        (default)
#   scripts/serve_vllm.sh gemma4            # Gemma 4 31B FP8, one GPU
#   scripts/serve_vllm.sh qwen36            # Qwen3.6-35B-A3B-FP8 MoE, one GPU, fast sampler
#   scripts/serve_vllm.sh qwen38-bf16       # Qwen3.8-27B bf16, tensor parallel over both GPUs
#   scripts/serve_vllm.sh qwen35-122b       # Qwen3.5-122B-A10B GPTQ-Int4, both GPUs
#
# Two single-card presets run side by side:
#   GPU=0 PORT=8000 scripts/serve_vllm.sh qwen38
#   GPU=1 PORT=8001 scripts/serve_vllm.sh gemma4
# and the pipeline picks one with ECHOES_LOCAL_BASE_URL / ECHOES_LOCAL_MODEL.
#
# DRY_RUN=1 prints the composed command instead of running it.
#
# Install once:  uv tool install vllm   (or: pip install vllm  in a separate venv)
# vLLM >= 0.21 is needed: Qwen3.8 support, and Gemma 4 local layers no longer allocated
# at full length in the KV cache.
set -euo pipefail

PRESET="${1:-qwen38}"
PORT="${PORT:-8000}"
GPU="${GPU:-0}"
MAX_LEN="${MAX_LEN:-32768}"       # ~17k tokens per request (prompt, 2 few-shot pages, page, 5 bands)
MAX_IMAGES="${MAX_IMAGES:-10}"    # lower to 8 first if vLLM reports too little KV cache

COMMON=(
  --port "$PORT"
  --served-model-name "$PRESET"
  --max-model-len "$MAX_LEN"
  --max-num-seqs 8                       # the Qwen hybrids pre-allocate recurrent state per slot
  --limit-mm-per-prompt "{\"image\": $MAX_IMAGES}"
  --gpu-memory-utilization 0.92
  --enable-prefix-caching                 # system prompt and few-shot pages are shared by every request
  --trust-remote-code
)

case "$PRESET" in
  qwen38)
    # ~27 GiB weights, ~14 GiB left for KV (about 7 sequences of 32k)
    MODEL="Qwen/Qwen3.8-27B-FP8"
    DEVICES="$GPU"
    EXTRA=(--tensor-parallel-size 1 --reasoning-parser qwen3)
    ;;
  gemma4)
    # ~29 GiB weights with the vision tower kept, ~12 GiB left for KV
    MODEL="RedHatAI/gemma-4-31B-it-FP8-block"
    DEVICES="$GPU"
    EXTRA=(--tensor-parallel-size 1)
    ;;
  qwen36)
    # ~33 GiB weights, ~8 GiB left for KV (still 13 sequences: only 10 of 40 layers keep a cache)
    MODEL="Qwen/Qwen3.6-35B-A3B-FP8"
    DEVICES="$GPU"
    EXTRA=(--tensor-parallel-size 1 --reasoning-parser qwen3)
    ;;
  qwen38-bf16)
    # one-off accuracy check against the FP8 default: 25 GiB weights per card
    MODEL="Qwen/Qwen3.8-27B"
    DEVICES="${DEVICES:-0,1}"
    EXTRA=(--tensor-parallel-size 2 --reasoning-parser qwen3)
    ;;
  qwen35-122b)
    # ~62 GiB of int4 weights, 31 per card; do not add --quantization moe_wna16
    MODEL="${QWEN35_122B_MODEL:-Qwen/Qwen3.5-122B-A10B-GPTQ-Int4}"
    DEVICES="${DEVICES:-0,1}"
    EXTRA=(--tensor-parallel-size 2 --reasoning-parser qwen3)
    ;;
  *)
    echo "unknown preset $PRESET" >&2; exit 1 ;;
esac

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-$DEVICES}"
echo "Serving $MODEL as '$PRESET' on http://localhost:$PORT/v1 (GPU $CUDA_VISIBLE_DEVICES)"
echo "export ECHOES_LOCAL_BASE_URL=http://localhost:$PORT/v1 ECHOES_LOCAL_MODEL=$PRESET"
if [[ "${DRY_RUN:-0}" == "1" ]]; then
  printf '%q ' vllm serve "$MODEL" "${COMMON[@]}" "${EXTRA[@]}"; echo
  exit 0
fi
exec vllm serve "$MODEL" "${COMMON[@]}" "${EXTRA[@]}"
