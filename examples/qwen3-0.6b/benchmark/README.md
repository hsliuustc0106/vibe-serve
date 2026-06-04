# Benchmark notes

Optional custom benchmark for the qwen3-0.6b target.

The harness entrypoint used in the baseline workflow is
`scripts/run_benchmark.sh`, which uses `vllm bench serve` directly.

If you use `benchmark/benchmark.py`, it sends OpenAI-compatible streaming
completions to `/v1/completions` and reports wall-clock throughput (`tokens_per_sec`).

## Default shape

- prompt: fixed short text
- max tokens: 128
- temperature: 0
- concurrency: 1 (for checker-like smoke), configurable via `--concurrency`

