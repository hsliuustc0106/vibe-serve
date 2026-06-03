# benchmark/benchmark.py

Code-edit latency benchmark on `m-a-p/CodeEditorBench` code-debug rows. Drives an OpenAI-compatible `/v1/completions` server. The default remains concurrency = 1 for the paper-style single-batch predicted-outputs target, and the benchmark also supports explicit concurrency sweeps for baseline comparison.

## What it sends

Each request body:

```json
{
  "prompt": "<chat-templated instruction containing the buggy ```python3 ...``` block>",
  "prediction": {"type": "content", "content": "<the buggy original code, verbatim>"},
  "max_tokens": 512,
  "temperature": 0,
  "stream": true,
  "prompt_is_preformatted": true
}
```

`prediction.content` is OpenAI's [predicted-outputs](https://developers.openai.com/api/docs/guides/predicted-outputs) field. vLLM/SGLang ignore it today (the request still parses and runs as a normal completion); a server that consumes the field is the configuration this benchmark scores.

## What it captures (per sample)

For each successful response, in addition to the standard latency / TTFT / TPOT:

- **Token-level alignment vs the prediction**: for each accepted output, tokenize both the buggy input and the model's output with the Qwen3 tokenizer, run a `difflib.SequenceMatcher` on the token-id sequences, and record:
  - `num_matched_tokens`, `num_diverged_tokens`
  - `matched_run_lengths` — list of token-lengths of every "equal" block in the output
  - `longest_matched_run`
- **Quality**: `ratio_to_gold`, `ratio_to_input`, `equals_input_verbatim`. The gate `ratio_to_gold > ratio_to_input` distinguishes a real fix from "echo the buggy input back."

These fields are what an analytical predicted-outputs headroom estimate would consume — the bench just emits them, the math lives downstream.

## Token count canonicalisation

`output_tokens` is computed by re-tokenising the concatenated server response — independent of how many tokens the server batches per SSE chunk. vLLM/SGLang flush all accepted spec tokens in one chunk, which would otherwise massively undercount tok/s. `num_chunks` is reported separately so you can also see effective spec accept length.

## Headline metric

```
Primary metric: median_tok_per_sec = ...
```

This is what `perf_metric` records and what the orchestrator's plateau detector compares across rounds.

## Running

```bash
uv run python benchmark.py \
    --url http://localhost:8000 \
    --num-samples 50 --warmup 3 \
    --max-tokens 512 \
    --output-json /tmp/code_edit.json
```

Default `--languages python3`. To include cpp/java rows: `--languages python3,cpp,java`. Token-level alignment math is cleanest on Python (BPE chunking interacts well with the dataset's whitespace), so default is python3 only.

The benchmark load shape matches the vLLM online benchmark's maximum-throughput
pattern: unlimited request rate with bounded in-flight requests. To compare
across load levels, use either a single concurrency:

```bash
uv run python benchmark.py \
    --url http://localhost:8000 \
    --num-samples 64 --warmup 4 \
    --concurrency 8 \
    --output-json /tmp/code_edit_c8.json
```

or a sweep:

```bash
uv run python benchmark.py \
    --url http://localhost:8000 \
    --num-samples 64 --warmup 4 \
    --sweep-concurrency 1,2,4,8,16,32 \
    --output-json /tmp/code_edit_sweep.json
```

Sweep output contains a top-level `summary` table plus per-concurrency run details.

The wrapper `../scripts/run_benchmark.sh` exposes the same idea with
vLLM-style environment variable names:

```bash
VIBESERVE_URL=http://localhost:8000 \
VIBESERVE_BENCH_SWEEP_CONCURRENCY=1,2,4,8,16 \
  ../scripts/run_benchmark.sh
```

## vLLM baseline workflow

The target-level baseline helper lives at
`../baseline/run_vllm_baseline.sh`. It creates a separate uv virtualenv for the
latest vLLM wheel, starts `vllm serve`, waits for `/health`, and then runs this
benchmark against vLLM's OpenAI-compatible `/v1/completions` endpoint. It uses
this benchmark instead of generic ShareGPT so the baseline receives the same
preformatted CodeEditorBench prompts and `prediction.content` envelope as
VibeServe-generated engines.

```bash
CUDA_VISIBLE_DEVICES=0 \
VLLM_MODEL=/model \
VLLM_BENCH_TOKENIZER=/model \
VLLM_BENCH_SWEEP_CONCURRENCY=1,2,4,8 \
  ../baseline/run_vllm_baseline.sh
```
