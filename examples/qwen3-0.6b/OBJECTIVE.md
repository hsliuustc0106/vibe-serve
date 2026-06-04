# Objective — Qwen3-0.6B single-device baseline

Measure a single-device `Qwen/Qwen3-0.6B` serving stack on `/v1/completions`.

## Performance target

- Build an OpenAI-compatible server with `/health`, `/v1/models`, and `/v1/completions`.
- Compare generated runs against the vLLM single-device baseline using
  `vllm bench serve` with:
  - one warmup request,
  - `random-input-len=512`, `random-output-len=128`,
  - `max-concurrency=32`, `num-prompts=64`,
  - `request-rate=inf`, `ignore_eos`.
- Primary optimization target is output token throughput.

## Scope

This target focuses on deployment shape and systems-level optimization.
Accuracy remains required but the first milestone is a clean baseline capture
and repeatable benchmark harness for this model on one CUDA device.

