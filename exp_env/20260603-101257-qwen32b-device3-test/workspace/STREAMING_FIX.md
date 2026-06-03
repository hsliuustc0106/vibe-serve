# Streaming output fix

This run snapshot updates the generated starter server so `/v1/completions`
streams token chunks during generation instead of emitting one final SSE chunk
after generation completes.

The change lets `vllm bench serve` measure TTFT and TPOT against the starter
engine using the same streaming semantics as vLLM.

Validation performed on the run workspace:

- `python -m py_compile main.py`
- Manual streaming probe observed incremental chunks.
- `vllm bench serve` probe with random input/output `32/8` reported nonzero
  TPOT (`743.40 ms`) instead of the previous near-zero artifact.
