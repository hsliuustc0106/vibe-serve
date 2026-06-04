"""
Accuracy checker for the qwen3-0.6b baseline target.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _post_json(url: str, body: dict[str, Any], timeout: float = 120.0) -> dict[str, Any]:
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read().decode("utf-8")
        return json.loads(data)


def _get_health(url: str) -> None:
    with urllib.request.urlopen(url, timeout=120) as resp:
        if resp.status != 200:
            raise RuntimeError(f"/health status={resp.status}")


def _validate_completion(resp: dict[str, Any]) -> None:
    choices = resp.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("missing or invalid choices in completion response")
    if "text" not in choices[0]:
        raise ValueError("completion.choice does not contain text")


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-check endpoint and response shape")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--num-samples", type=int, default=3)
    parser.add_argument("--output-json", default="/tmp/qwen3_0.6b_checker.json")
    parser.add_argument("--max-tokens", type=int, default=16)
    args = parser.parse_args()

    t0 = time.perf_counter()
    try:
        _get_health(f"{args.url.rstrip('/')}/health")
    except Exception as exc:  # pragma: no cover - fail-fast with useful context
        raise SystemExit(f"health check failed: {exc}") from exc

    failures = 0
    actual_samples = max(args.num_samples, 1)
    for _ in range(actual_samples):
        try:
            response = _post_json(
                f"{args.url.rstrip('/')}/v1/completions",
                {
                    "model": "Qwen/Qwen3-0.6B",
                    "prompt": "The capital of France is",
                    "temperature": 0.0,
                    "max_tokens": args.max_tokens,
                    "stream": False,
                },
            )
            _validate_completion(response)
        except (OSError, urllib.error.URLError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            failures += 1
            print(f"sample failed: {exc}", file=sys.stderr)

    latency_ms = (time.perf_counter() - t0) * 1000.0
    result = {
        "num_samples": actual_samples,
        "failed": failures,
        "passed": actual_samples - failures,
        "latency_ms": latency_ms,
    }

    out = Path(args.output_json)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
