#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENGINE_DIR="${VIBESERVE_ENGINE_DIR:-$(pwd)}"
APP_MODULE="${VIBESERVE_APP_MODULE:-starter.main:app}"
HOST="${VIBESERVE_HOST:-0.0.0.0}"
PORT="${VIBESERVE_PORT:-8000}"

cd "$ENGINE_DIR"
exec uv run --project "$PROJECT_ROOT" python -m uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT"
