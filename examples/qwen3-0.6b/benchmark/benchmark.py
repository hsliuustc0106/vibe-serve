"""Minimal benchmark driver for the qwen3-0.6b example bundle."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx


PROMPTS = [
    "The capital of France is",
    "Once upon a time in a land far away,",
    "In Python, write a quick sort function.",
    "Explain the concept of attention in a transformer.",
]


async def send_request(client: httpx.AsyncClient, url: str, prompt: str, max_tokens: int) -> dict[str, float | int]:
    body = {"prompt": prompt, "max_tokens": max_tokens, "temperature": 0, "stream": True}
    t_send = time.perf_counter()
    t_first = None
    t_done = None
    output_tokens = 0
    first_line = True

    async with client.stream("POST", url, json=body, timeout=120.0) as resp:
        resp.raise_for_status()
        async for raw_line in resp.aiter_lines():
            if not raw_line.startswith("data: "):
                continue
            payload = raw_line[6:]
            if payload.strip() == "[DONE]":
                t_done = time.perf_counter()
                break
            chunk = json.loads(payload)
            delta = chunk["choices"][0].get("text", "")
            if first_line and delta:
                t_first = time.perf_counter()
                first_line = False
            output_tokens += 1 if delta else 0

    if t_first is None:
        t_first = t_send
    if t_done is None:
        t_done = time.perf_counter()

    return {
        "ttft": t_first - t_send,
        "tpot": (t_done - t_first) / max(output_tokens, 1),
        "latency": t_done - t_send,
        "output_tokens": output_tokens,
    }


async def run_benchmark(url: str, num_requests: int, concurrency: int, max_tokens: int) -> dict:
    sem = asyncio.Semaphore(max(concurrency, 1))
    stats: list[dict] = []

    async def run_one(prompt: str) -> dict:
        async with sem:
            return await send_request(
                client,
                f"{url.rstrip('/')}/v1/completions",
                prompt,
                max_tokens,
            )

    start = time.perf_counter()
    async with httpx.AsyncClient() as client:
        prompts = [PROMPTS[i % len(PROMPTS)] for i in range(num_requests)]
        tasks = [asyncio.create_task(run_one(prompt)) for prompt in prompts]
        stats = await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = time.perf_counter() - start
    ok = [x for x in stats if isinstance(x, dict)]
    errors = num_requests - len(ok)
    total_output = sum(x.get("output_tokens", 0) for x in ok)
    wall_clock = max(elapsed, 1e-9)
    success_rate = len(ok) / num_requests if num_requests else 0.0
    return {
        "requests": num_requests,
        "success": len(ok),
        "errors": errors,
        "elapsed": elapsed,
        "success_rate": success_rate,
        "tokens_per_sec": total_output / wall_clock,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal qwen3-0.6b benchmark")
    parser.add_argument("--url", required=True, help="Base server URL")
    parser.add_argument("--num-samples", type=int, default=64)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--concurrency", type=int, default=32)
    parser.add_argument("--output-json", default="/tmp/qwen3_0.6b_bench.json")
    args = parser.parse_args()

    result = asyncio.run(
        run_benchmark(args.url, args.num_samples, args.concurrency, args.max_tokens)
    )
    Path(args.output_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
