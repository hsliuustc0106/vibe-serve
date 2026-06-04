# qwen3-0.6b — first model baseline target

Target bundle for the Qwen 0.6B baseline workflow.

```
qwen3-0.6b/
├── OBJECTIVE.md                       # target objective
├── goal.json                          # benchmark contract + acceptance targets
├── README.md                          # this file
├── scripts/
│   ├── run_server.sh                  # launch a starter uvicorn server
│   ├── run_checker.sh                 # run a basic endpoint smoke checker
│   └── run_benchmark.sh               # vLLM-bench wrapper for headline runs
├── baseline/
│   └── run_vllm_baseline.sh           # single-device vLLM baseline with model predownload
├── benchmark/
│   ├── benchmark.py                   # optional custom benchmark driver
│   └── README.md
├── accuracy_checker/
│   ├── checker.py                     # basic endpoint sanity checker
│   └── README.md
└── reference/
    ├── README.md                      # how the model is mounted in the workspace
    └── meta.json                      # HF model id used by the environment
```

The baseline entrypoint is:

```bash
./examples/qwen3-0.6b/baseline/run_vllm_baseline.sh
```

It downloads `Qwen/Qwen3-0.6B` first (unless a local path is passed in
`VLLM_MODEL`), starts `vllm serve` with a one-device layout, and runs:

- warmup: 1 request
- measured load: `max-concurrency=32`, `num-prompts=64`
- random input/output tokens: `512/128`

Results are written under `baseline/vllm_bench_results` by default.

