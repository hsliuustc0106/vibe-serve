# qwen3-32b-code-edit — predicted-outputs benchmark

This input bundle measures an OpenAI-compatible completion server for `Qwen/Qwen3-32B`. The headline throughput runner uses `vllm bench serve` against `/v1/completions` so vLLM baselines and generated servers are driven by the same benchmark client. The code-edit benchmark still lives in `benchmark/benchmark.py` for predicted-output analysis and correctness-oriented development.

## Why this dataset

CodeEditorBench's "code debug" rows hand the model an `incorrect_solutions` (the buggy code) and ask it to emit `solutions` (the same code with the bug fixed). On Python3 rows, **median character overlap between the two is 99.6%**, and 75% of matched runs are >16 chars long. That is exactly the regime predicted outputs is designed for: the model's output is dominated by long verbatim copies of a known prediction with a few small islands of new tokens.

`benchmark/benchmark.py` records, per sample, the token-level alignment between the actual model output and the prediction (matched-run lengths, longest run, total matched/diverged tokens). Those numbers are what an analytical headroom calculation would feed on.

## Layout

```
qwen3-32b-code-edit/
├── OBJECTIVE.md                       # the goal handed to vibeserve-orchestrate
├── goal.json                          # machine-readable target contract
├── README.md                          # this file
├── benchmark/
│   ├── benchmark.py                   # /v1/completions driver, single-batch
│   └── README.md
├── accuracy_checker/
│   ├── checker.py                     # quality gate — prevents echo-input bypass
│   └── README.md
├── reference/
│   ├── README.md                      # how to mount the target model
│   └── meta.json                      # pinned model ids
├── scripts/
    ├── run_server.sh                  # start a generated uvicorn engine
    ├── run_checker.sh                 # run the correctness gate
    └── run_benchmark.sh               # run the vLLM bench headline benchmark
└── baseline/
    └── run_vllm_baseline.sh           # create an isolated uv vLLM env and run baseline
```

`goal.json` is the narrow target contract the agent should optimize against. It records the model, one-device CUDA constraint, required OpenAI-compatible endpoints, correctness gate, benchmark metric, forbidden shortcuts, and staged validation order.

## Request envelope

The benchmark drives an OpenAI-compatible `/v1/completions` endpoint. Every request body is:

```json
{
  "prompt": "<chat-templated instruction containing the buggy code>",
  "prediction": {"type": "content", "content": "<the buggy original code, verbatim>"},
  "max_tokens": 512,
  "temperature": 0,
  "stream": true,
  "prompt_is_preformatted": true
}
```

The `prediction` field is the OpenAI predicted-outputs format. Servers that don't implement it (vLLM, SGLang today) just ignore it; a server that does implement it is the configuration this benchmark scores.

## How to run

Launch the server, then:

```bash
VIBESERVE_URL=http://localhost:8000 \
  ./examples/qwen3-32b-code-edit/scripts/run_benchmark.sh
```

`run_benchmark.sh` creates an isolated uv environment for the benchmark client
and installs the latest `vllm` wheel by default. It runs one warmup request
first, then the two headline `vllm bench serve` maximum-throughput cases:

- `max-concurrency=1`, `num-prompts=4`, random input/output tokens `1024/128`
- `max-concurrency=8`, `num-prompts=32`, random input/output tokens `1024/128`

The benchmark uses `request-rate=inf`, `temperature=0`, `--ignore-eos`, and
the OpenAI `/v1/completions` endpoint. Results are written to
`/tmp/qwen3_code_edit_vllm_bench` by default.

Common knobs:

- `VIBESERVE_BENCH_OUT_DIR` — result directory.
- `VIBESERVE_BENCH_UV_ENV` — uv virtualenv path for the benchmark client.
- `VIBESERVE_BENCH_VLLM_INSTALL_SPEC` — vLLM package spec for the benchmark client.
- `VIBESERVE_BENCH_WARMUP_PROMPTS` — warmup prompt count; defaults to `1`.
- `VIBESERVE_BENCH_RANDOM_INPUT_LEN`, `VIBESERVE_BENCH_RANDOM_OUTPUT_LEN` — random workload token lengths; default to `1024` and `128`.
- `VIBESERVE_BENCH_CASES` — comma-separated `concurrency:num_prompts` cases; defaults to `1:4,8:32`.

## vLLM baseline

Use `baseline/run_vllm_baseline.sh` to measure a vLLM baseline with the same
headline client used for generated servers. The script follows the vLLM
online-benchmark workflow: start an OpenAI-compatible `vllm serve` process,
wait for `/health`, then drive `/v1/completions` with `vllm bench serve`.

The baseline intentionally creates an isolated uv environment at
`examples/qwen3-32b-code-edit/.venv-vllm` and installs the latest `vllm` wheel
by default. To pin or test a specific vLLM build, override
`VLLM_INSTALL_SPEC`, for example `VLLM_INSTALL_SPEC='vllm==0.10.0'` or a wheel
URL supported by `uv pip install`.

```bash
# Optional: reuse an already-downloaded local snapshot.
export VLLM_MODEL=/model

# Optional: restrict the server to one visible GPU.
export CUDA_VISIBLE_DEVICES=0

./examples/qwen3-32b-code-edit/baseline/run_vllm_baseline.sh
```

Common knobs:

- `VLLM_UV_ENV` — uv virtualenv path for the vLLM installation.
- `VLLM_INSTALL_SPEC` — package spec installed into that env; defaults to latest `vllm`.
- `VLLM_MODEL` — model served by vLLM; defaults to `Qwen/Qwen3-32B`.
- `VLLM_SERVED_MODEL_NAME` — model name sent by the benchmark; defaults to `Qwen/Qwen3-32B`.
- `VLLM_SERVER_ARGS` — extra arguments appended to `vllm serve`.
- `VLLM_BENCH_OUT_DIR` — result directory; defaults to `baseline/vllm_bench_results`.

Example headline baseline:

```bash
CUDA_VISIBLE_DEVICES=0 \
VLLM_MODEL=/model \
  ./examples/qwen3-32b-code-edit/baseline/run_vllm_baseline.sh
```

To run a generated server from an accepted candidate workspace:

```bash
VIBESERVE_ENGINE_DIR=/path/to/generated/workspace \
VIBESERVE_APP_MODULE=starter.main:app \
  ./examples/qwen3-32b-code-edit/scripts/run_server.sh
```

To run the correctness gate:

```bash
VIBESERVE_URL=http://localhost:8000 \
  ./examples/qwen3-32b-code-edit/scripts/run_checker.sh
```

## Accuracy gate

`accuracy_checker/checker.py` is the anti-reward-hacking gate. It enforces:

- Output must be **closer to the gold solution than to the buggy input** (a server that just echoes the prediction back fails this).
- Output must not equal the buggy input verbatim (degenerate "no edit" bypass).

These gates are intentionally cheap so they don't dominate the perf budget — the harder integration test is left to `bench/benchmark.py`'s per-sample diff stats.
