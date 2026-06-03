#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

VLLM_UV_ENV="${VLLM_UV_ENV:-$ROOT_DIR/.venv-vllm}"
VLLM_INSTALL_SPEC="${VLLM_INSTALL_SPEC:-vllm}"
VLLM_MODEL="${VLLM_MODEL:-Qwen/Qwen3-32B}"
VLLM_SERVED_MODEL_NAME="${VLLM_SERVED_MODEL_NAME:-Qwen/Qwen3-32B}"
VLLM_HOST="${VLLM_HOST:-127.0.0.1}"
VLLM_PORT="${VLLM_PORT:-8000}"
VLLM_DTYPE="${VLLM_DTYPE:-bfloat16}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-32768}"
VLLM_READY_TIMEOUT="${VLLM_READY_TIMEOUT:-900}"

BENCH_SAMPLES="${VLLM_BENCH_SAMPLES:-50}"
BENCH_WARMUP="${VLLM_BENCH_WARMUP:-3}"
BENCH_MAX_TOKENS="${VLLM_BENCH_MAX_TOKENS:-512}"
BENCH_SWEEP_CONCURRENCY="${VLLM_BENCH_SWEEP_CONCURRENCY:-1}"
BENCH_OUT="${VLLM_BENCH_OUT:-$ROOT_DIR/baseline/vllm_baseline_sweep.json}"
BENCH_TOKENIZER="${VLLM_BENCH_TOKENIZER:-$VLLM_MODEL}"

mkdir -p "$(dirname "$BENCH_OUT")"

if [[ ! -x "$VLLM_UV_ENV/bin/python" ]]; then
  uv venv --python "${VLLM_PYTHON:-python3}" "$VLLM_UV_ENV"
fi

uv pip install --python "$VLLM_UV_ENV/bin/python" --upgrade \
  "$VLLM_INSTALL_SPEC" \
  datasets \
  transformers \
  httpx

SERVER_LOG="${VLLM_SERVER_LOG:-$ROOT_DIR/baseline/vllm_server.log}"
rm -f "$SERVER_LOG"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

read -r -a EXTRA_SERVER_ARGS <<< "${VLLM_SERVER_ARGS:-}"

"$VLLM_UV_ENV/bin/vllm" serve "$VLLM_MODEL" \
  --served-model-name "$VLLM_SERVED_MODEL_NAME" \
  --host "$VLLM_HOST" \
  --port "$VLLM_PORT" \
  --dtype "$VLLM_DTYPE" \
  --max-model-len "$VLLM_MAX_MODEL_LEN" \
  "${EXTRA_SERVER_ARGS[@]}" \
  >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

deadline=$((SECONDS + VLLM_READY_TIMEOUT))
until curl -fsS "http://$VLLM_HOST:$VLLM_PORT/health" >/dev/null 2>&1; do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "vLLM server exited before readiness. Log follows:" >&2
    cat "$SERVER_LOG" >&2
    exit 1
  fi
  if (( SECONDS >= deadline )); then
    echo "Timed out waiting for vLLM readiness at http://$VLLM_HOST:$VLLM_PORT/health" >&2
    tail -200 "$SERVER_LOG" >&2 || true
    exit 1
  fi
  sleep 2
done

cd "$ROOT_DIR"
"$VLLM_UV_ENV/bin/python" benchmark/benchmark.py \
  --url "http://$VLLM_HOST:$VLLM_PORT" \
  --model "$VLLM_SERVED_MODEL_NAME" \
  --tokenizer-path "$BENCH_TOKENIZER" \
  --num-samples "$BENCH_SAMPLES" \
  --warmup "$BENCH_WARMUP" \
  --max-tokens "$BENCH_MAX_TOKENS" \
  --sweep-concurrency "$BENCH_SWEEP_CONCURRENCY" \
  --output-json "$BENCH_OUT"

echo "vLLM baseline result: $BENCH_OUT"
echo "vLLM server log: $SERVER_LOG"
