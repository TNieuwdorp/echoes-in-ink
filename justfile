# Echoes in Ink task runner. Install `just` (https://just.systems) or copy the commands.

set dotenv-load := true

default:
    @just --list

# Install Python deps and the UI toolchain
setup:
    uv sync --extra dev
    cd ui && npm install

# Download model weights (presets: qwen38 qwen38-fp8 gemma4 qwen36 qwen35-122b)
download +presets="qwen38":
    scripts/download_models.sh {{presets}}

# Start the local vLLM server for a preset (env: GPU=0 PORT=8000 MAX_LEN=32768 DRY_RUN=1)
serve preset="qwen38":
    scripts/serve_vllm.sh {{preset}}

# Register and preprocess every image in a directory
ingest dir:
    uv run echoes ingest {{dir}}
    uv run echoes preprocess

# Benchmark a served preset on the sample pages (needs `just serve` running on that port)
bench model="qwen38" port="8000":
    uv run echoes ingest tests/fixtures
    uv run echoes preprocess
    ECHOES_LOCAL_BASE_URL=http://localhost:{{port}}/v1 ECHOES_LOCAL_MODEL={{model}} uv run echoes transcribe --engine local --samples 3 --with-bands
    uv run echoes reconcile
    uv run echoes evaluate --detail

# Transcribe everything that is registered (greedy + sampled passes with bands)
transcribe model="qwen38" port="8000":
    ECHOES_LOCAL_BASE_URL=http://localhost:{{port}}/v1 ECHOES_LOCAL_MODEL={{model}} uv run echoes transcribe --engine local --samples 3 --with-bands
    uv run echoes reconcile --correct-with local

# Measure the cloud quality ceiling on the gold pages only. No API key needed: uses the
# logged-in Claude Code CLI (`claude auth status`); set ANTHROPIC_API_KEY to bill the API instead.
ceiling:
    uv run echoes transcribe --engine claude --samples 1 --with-bands

# Review UI: FastAPI backend + Vite dev server with hot reload
review:
    (uv run echoes serve &) && cd ui && npm run dev

# Build the static family site into ui/dist
site:
    uv run echoes export
    cd ui && npm run build

test:
    uv run pytest -q
    uv run ruff check src tests
