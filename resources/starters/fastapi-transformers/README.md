# FastAPI + Transformers Starter

This starter is a conservative baseline for text-generation targets. It gives
the agent a runnable serving stack before any optimization work starts.

## What It Provides

- `GET /health`
- `GET /v1/models`
- `POST /v1/completions`
- non-streaming OpenAI-like completion responses
- streaming SSE responses ending with `data: [DONE]`
- lazy Hugging Face tokenizer/model loading
- `run_benchmark.sh` for a vLLM online-benchmark-style headline throughput check

## Running

```bash
MODEL_ID=Qwen/Qwen3-32B \
WEIGHTS_DIR=/model \
./run_server.sh
```

By default, `WEIGHTS_DIR` is preferred when it exists. Otherwise the server uses
`MODEL_ID`, allowing small local smoke tests with a public Hugging Face model.

```bash
VIBESERVE_URL=http://localhost:8000 \
VIBESERVE_MODEL=Qwen/Qwen3-32B \
./run_benchmark.sh
```

The benchmark runner creates an isolated uv environment for the latest vLLM
client by default, sends one warmup request, then runs the default measured case
with `max-concurrency=1`, `num-prompts=4`, and random input/output lengths
`1024/128`. Override `VIBESERVE_BENCH_CASES` for additional
`concurrency:num_prompts` cases.

## Expected Agent Use

Copy this directory into the workspace root, then optimize from it. Keep
checker and benchmark artifacts read-only and target all changes at the server
implementation.
