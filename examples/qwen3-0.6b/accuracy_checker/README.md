# Accuracy checker

Basic smoke checker for Qwen3-0.6B endpoint readiness and response shape.

Usage:

```bash
VIBESERVE_URL=http://localhost:8000 uv run python accuracy_checker/checker.py
```

The checker validates:

- `/health` returns HTTP 200.
- `/v1/completions` accepts a tiny prompt at temperature 0.
- The response contains at least one completion choice with text.
- A short JSON summary is emitted to the requested output path.

