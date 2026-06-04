#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

VLLM_UV_ENV="${VLLM_UV_ENV:-$ROOT_DIR/.venv-vllm}"
VLLM_INSTALL_SPEC="${VLLM_INSTALL_SPEC:-vllm}"
VLLM_MODEL="${VLLM_MODEL:-Qwen/Qwen3-0.6B}"
VLLM_SERVED_MODEL_NAME="${VLLM_SERVED_MODEL_NAME:-Qwen/Qwen3-0.6B}"
VLLM_HOST="${VLLM_HOST:-127.0.0.1}"
VLLM_PORT="${VLLM_PORT:-8000}"
VLLM_DTYPE="${VLLM_DTYPE:-bfloat16}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-32768}"
VLLM_READY_TIMEOUT="${VLLM_READY_TIMEOUT:-900}"
VLLM_VISIBLE_DEVICES="${VLLM_VISIBLE_DEVICES:-0}"

BENCH_OUT_DIR="${VLLM_BENCH_OUT_DIR:-$ROOT_DIR/baseline/vllm_bench_results}"

mkdir -p "$BENCH_OUT_DIR"

if [[ ! -x "$VLLM_UV_ENV/bin/python" ]]; then
  uv venv --python "${VLLM_PYTHON:-python3}" "$VLLM_UV_ENV"
fi

uv pip install --python "$VLLM_UV_ENV/bin/python" --upgrade \
  "$VLLM_INSTALL_SPEC" \
  datasets \
  transformers \
  huggingface_hub \
  httpx

if [[ "${VLLM_SKIP_DOWNLOAD:-0}" != "1" && "$VLLM_MODEL" != "/"* && ! -e "$VLLM_MODEL" ]]; then
  if [[ -n "${CUDA_VISIBLE_DEVICES:-}" ]]; then
    :
  else
    export CUDA_VISIBLE_DEVICES="$VLLM_VISIBLE_DEVICES"
  fi

  echo "Prefetching model from Hugging Face Hub: $VLLM_MODEL"
  "$VLLM_UV_ENV/bin/python" - <<'PY'
import os
from huggingface_hub import snapshot_download

model_id = os.environ["VLLM_MODEL"]
snapshot_download(repo_id=model_id, resume_download=True)
print(f"Model snapshot ready: {model_id}")
PY
fi

SERVER_LOG="${VLLM_SERVER_LOG:-$ROOT_DIR/baseline/vllm_server.log}"
rm -f "$SERVER_LOG"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if [[ -z "${CUDA_VISIBLE_DEVICES:-}" && -n "${VLLM_VISIBLE_DEVICES:-}" ]]; then
  export CUDA_VISIBLE_DEVICES="$VLLM_VISIBLE_DEVICES"
fi

EXTRA_SERVER_ARGS=()
if [[ -n "${VLLM_SERVER_ARGS:-}" ]]; then
  read -r -a EXTRA_SERVER_ARGS <<< "$VLLM_SERVER_ARGS"
fi
"$VLLM_UV_ENV/bin/vllm" serve "$VLLM_MODEL" \
  --served-model-name "$VLLM_SERVED_MODEL_NAME" \
  --host "$VLLM_HOST" \
  --port "$VLLM_PORT" \
  --dtype "$VLLM_DTYPE" \
  --max-model-len "$VLLM_MAX_MODEL_LEN" \
  --tensor-parallel-size 1 \
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

VIBESERVE_URL="http://$VLLM_HOST:$VLLM_PORT" \
VIBESERVE_MODEL="$VLLM_SERVED_MODEL_NAME" \
VIBESERVE_BENCH_RANDOM_INPUT_LEN="${VLLM_BENCH_RANDOM_INPUT_LEN:-512}" \
VIBESERVE_BENCH_RANDOM_OUTPUT_LEN="${VLLM_BENCH_RANDOM_OUTPUT_LEN:-128}" \
VIBESERVE_BENCH_CASES="${VLLM_BENCH_CASES:-32:64}" \
VIBESERVE_BENCH_WARMUP_PROMPTS="${VLLM_BENCH_WARMUP_PROMPTS:-1}" \
VIBESERVE_BENCH_UV_ENV="${VLLM_UV_ENV}" \
VIBESERVE_BENCH_VLLM_INSTALL_SPEC="${VLLM_BENCH_VLLM_INSTALL_SPEC:-vllm}" \
VIBESERVE_BENCH_OUT_DIR="$BENCH_OUT_DIR" \
  "$ROOT_DIR/scripts/run_benchmark.sh"

echo "vLLM baseline results: $BENCH_OUT_DIR"
echo "vLLM server log: $SERVER_LOG"
