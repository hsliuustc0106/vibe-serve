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

## Running

```bash
MODEL_ID=Qwen/Qwen3-32B \
WEIGHTS_DIR=/model \
./run_server.sh
```

By default, `WEIGHTS_DIR` is preferred when it exists. Otherwise the server uses
`MODEL_ID`, allowing small local smoke tests with a public Hugging Face model.

## Expected Agent Use

Copy this directory into the workspace root, then optimize from it. Keep
checker and benchmark artifacts read-only and target all changes at the server
implementation.
