#!/usr/bin/env bash
# Start a local vLLM server for one of the benchmark candidates.
#
#   scripts/serve_vllm.sh qwen38          # Qwen3.8-27B, bf16, both GPUs
#   scripts/serve_vllm.sh qwen38-fp8      # Qwen3.8-27B FP8 on GPU 0 (leaves GPU 1 free)
#   scripts/serve_vllm.sh gemma4          # Gemma 4 31B, both GPUs
#   scripts/serve_vllm.sh qwen36          # Qwen3.6-35B-A3B MoE, fast sampler
#   scripts/serve_vllm.sh qwen35-122b     # Qwen3.5-122B-A10B int4, both GPUs
#
# All serve an OpenAI-compatible API on http://localhost:8000/v1. The pipeline reads
# ECHOES_LOCAL_MODEL to know which model name to send; this script exports it for you
# when sourced, and prints it otherwise.
#
# Install once:  uv tool install vllm   (or: pip install vllm  in a separate venv)
# vLLM >= 0.11 is needed for Qwen3.8; check `vllm --version`.
set -euo pipefail

PRESET="${1:-qwen38}"
PORT="${PORT:-8000}"
COMMON=(
  --port "$PORT"
  --served-model-name "$PRESET"
  --max-model-len 32768            # full page + bands + 2 few-shot pages fit comfortably
  --limit-mm-per-prompt '{"image": 10}'
  --gpu-memory-utilization 0.92
  --enable-prefix-caching            # the system prompt and few-shot pages are shared by every request
  --trust-remote-code
)

case "$PRESET" in
  qwen38)
    MODEL="Qwen/Qwen3.8-27B"
    EXTRA=(--tensor-parallel-size 2 --reasoning-parser qwen3)
    ;;
  qwen38-fp8)
    MODEL="Qwen/Qwen3.8-27B-FP8"
    export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
    EXTRA=(--tensor-parallel-size 1 --reasoning-parser qwen3)
    ;;
  gemma4)
    MODEL="google/gemma-4-31B-it"
    EXTRA=(--tensor-parallel-size 2)
    ;;
  qwen36)
    MODEL="Qwen/Qwen3.6-35B-A3B"
    EXTRA=(--tensor-parallel-size 2 --reasoning-parser qwen3)
    ;;
  qwen35-122b)
    # pick an int4 checkpoint that exists on the Hub at the time you run this, e.g. an AWQ build
    MODEL="${QWEN35_122B_MODEL:-Qwen/Qwen3.5-122B-A10B-AWQ}"
    EXTRA=(--tensor-parallel-size 2 --reasoning-parser qwen3)
    ;;
  *)
    echo "unknown preset $PRESET" >&2; exit 1 ;;
esac

echo "Serving $MODEL as '$PRESET' on http://localhost:$PORT/v1"
echo "export ECHOES_LOCAL_MODEL=$PRESET"
exec vllm serve "$MODEL" "${COMMON[@]}" "${EXTRA[@]}"
