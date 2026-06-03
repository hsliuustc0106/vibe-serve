#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
URL="${VIBESERVE_URL:-http://localhost:8000}"
MODEL="${VIBESERVE_MODEL:-Qwen/Qwen3-32B}"
ENDPOINT="${VIBESERVE_BENCH_ENDPOINT:-/v1/completions}"
OUT_DIR="${VIBESERVE_BENCH_OUT_DIR:-/tmp/qwen3_code_edit_vllm_bench}"
UV_ENV="${VIBESERVE_BENCH_UV_ENV:-$ROOT_DIR/.venv-vllm-bench}"
INSTALL_SPEC="${VIBESERVE_BENCH_VLLM_INSTALL_SPEC:-vllm}"
PYTHON_BIN="${VIBESERVE_BENCH_PYTHON:-python3}"

WARMUP_PROMPTS="${VIBESERVE_BENCH_WARMUP_PROMPTS:-1}"
RANDOM_INPUT_LEN="${VIBESERVE_BENCH_RANDOM_INPUT_LEN:-1024}"
RANDOM_OUTPUT_LEN="${VIBESERVE_BENCH_RANDOM_OUTPUT_LEN:-128}"
CASES="${VIBESERVE_BENCH_CASES:-1:4}"

if [[ ! -x "$UV_ENV/bin/python" ]]; then
  uv venv --python "$PYTHON_BIN" "$UV_ENV"
fi

uv pip install --python "$UV_ENV/bin/python" --upgrade "$INSTALL_SPEC"

mkdir -p "$OUT_DIR"

run_case() {
  local concurrency="$1"
  local prompts="$2"
  local filename="$3"

  "$UV_ENV/bin/vllm" bench serve \
    --backend openai \
    --model "$MODEL" \
    --base-url "$URL" \
    --endpoint "$ENDPOINT" \
    --dataset-name random \
    --num-prompts "$prompts" \
    --random-input-len "$RANDOM_INPUT_LEN" \
    --random-output-len "$RANDOM_OUTPUT_LEN" \
    --request-rate inf \
    --max-concurrency "$concurrency" \
    --temperature 0 \
    --ignore-eos \
    --save-result \
    --result-dir "$OUT_DIR" \
    --result-filename "$filename"
}

echo "vLLM bench warmup: max-concurrency=1, num-prompts=$WARMUP_PROMPTS, random in/out=$RANDOM_INPUT_LEN/$RANDOM_OUTPUT_LEN"
run_case 1 "$WARMUP_PROMPTS" warmup.json

IFS=',' read -r -a CASE_LIST <<< "$CASES"
for item in "${CASE_LIST[@]}"; do
  concurrency="${item%%:*}"
  prompts="${item##*:}"
  if [[ -z "$concurrency" || -z "$prompts" || "$concurrency" == "$prompts" ]]; then
    echo "Invalid VIBESERVE_BENCH_CASES item '$item'; expected concurrency:num_prompts" >&2
    exit 1
  fi
  echo "vLLM bench measured case: max-concurrency=$concurrency, num-prompts=$prompts, random in/out=$RANDOM_INPUT_LEN/$RANDOM_OUTPUT_LEN"
  run_case "$concurrency" "$prompts" "c${concurrency}_n${prompts}.json"
done

echo "benchmark results: $OUT_DIR"
