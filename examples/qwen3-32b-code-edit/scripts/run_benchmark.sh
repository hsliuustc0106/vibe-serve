#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
URL="${VIBESERVE_URL:-http://localhost:8000}"
OUT="${VIBESERVE_BENCH_OUT:-/tmp/qwen3_code_edit_benchmark.json}"
SAMPLES="${VIBESERVE_BENCH_SAMPLES:-50}"
WARMUP="${VIBESERVE_BENCH_WARMUP:-3}"
TOKENIZER="${VIBESERVE_TOKENIZER:-Qwen/Qwen3-32B}"
MODEL="${VIBESERVE_MODEL:-Qwen/Qwen3-32B}"
MAX_TOKENS="${VIBESERVE_BENCH_MAX_TOKENS:-512}"
MAX_CONCURRENCY="${VIBESERVE_BENCH_MAX_CONCURRENCY:-${VIBESERVE_BENCH_CONCURRENCY:-1}}"
SWEEP_CONCURRENCY="${VIBESERVE_BENCH_SWEEP_CONCURRENCY:-}"

BENCH_ARGS=(
  --url "$URL"
  --model "$MODEL"
  --tokenizer-path "$TOKENIZER"
  --num-samples "$SAMPLES"
  --warmup "$WARMUP"
  --max-tokens "$MAX_TOKENS"
  --output-json "$OUT"
)

if [[ -n "$SWEEP_CONCURRENCY" ]]; then
  BENCH_ARGS+=(--sweep-concurrency "$SWEEP_CONCURRENCY")
  echo "vLLM-style benchmark: request-rate=inf, sweep max-concurrency=$SWEEP_CONCURRENCY"
else
  BENCH_ARGS+=(--concurrency "$MAX_CONCURRENCY")
  echo "vLLM-style benchmark: request-rate=inf, max-concurrency=$MAX_CONCURRENCY"
fi

cd "$ROOT_DIR"
uv run python benchmark/benchmark.py "${BENCH_ARGS[@]}"

echo "benchmark result: $OUT"
