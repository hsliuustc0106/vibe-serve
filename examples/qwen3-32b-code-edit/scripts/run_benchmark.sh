#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
URL="${VIBESERVE_URL:-http://localhost:8000}"
OUT="${VIBESERVE_BENCH_OUT:-/tmp/qwen3_code_edit_benchmark.json}"
SAMPLES="${VIBESERVE_BENCH_SAMPLES:-50}"
WARMUP="${VIBESERVE_BENCH_WARMUP:-3}"
TOKENIZER="${VIBESERVE_TOKENIZER:-Qwen/Qwen3-32B}"

cd "$ROOT_DIR"
uv run python benchmark/benchmark.py \
  --url "$URL" \
  --tokenizer-path "$TOKENIZER" \
  --num-samples "$SAMPLES" \
  --warmup "$WARMUP" \
  --output-json "$OUT"

echo "benchmark result: $OUT"
