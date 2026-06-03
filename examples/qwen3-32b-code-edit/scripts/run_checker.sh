#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
URL="${VIBESERVE_URL:-http://localhost:8000}"
OUT="${VIBESERVE_CHECKER_OUT:-/tmp/qwen3_code_edit_checker.json}"
SAMPLES="${VIBESERVE_CHECKER_SAMPLES:-10}"
TOKENIZER="${VIBESERVE_TOKENIZER:-Qwen/Qwen3-32B}"

cd "$ROOT_DIR"
uv run python accuracy_checker/checker.py \
  --url "$URL" \
  --tokenizer-path "$TOKENIZER" \
  --num-samples "$SAMPLES" \
  --output-json "$OUT"

echo "checker result: $OUT"
