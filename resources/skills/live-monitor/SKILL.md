---
name: live-monitor
description: >-
  Start and track the VibeServe live progress monitor for active runs.
---

# live-monitor

Use this skill whenever the user wants a live HTML status page for an
active run.

## How to use

1. Run the experiment with `--live-monitor` so the monitor starts automatically.
2. Optionally set `--live-monitor-port` (default `8765`) and
   `--live-monitor-open` to open the page in the default browser.
3. Since this skill is included in default `--skills-dir`, the agent can use it
   as its recommended way to keep runs visible during active optimization.
4. If the run is already happening, launch manually with:
   `bash scripts/monitor_run_progress.sh --run-dir <run_dir> --port <port>`.
5. Open `http://127.0.0.1:<port>/live_progress.html`.

## HTML placement contract

The live monitor HTML belongs under the run's report directory:

- Run root: `exp_env/<run-name>/`
- Report directory: `exp_env/<run-name>/reports/`
- Live page: `exp_env/<run-name>/reports/live_progress.html`
- Primary data source: `exp_env/<run-name>/reports/report.json`
- Optional vLLM target copy: `exp_env/<run-name>/reports/baseline_target.json`

Always serve the `reports/` directory, not the repository root and not
`exp_env/<run-name>/` directly. This keeps relative links simple:
`live_progress.html` fetches `report.json`, `baseline_target.json`, and
links such as `round_summary.json` from the same served directory.

The monitor launcher is responsible for creating or updating only
`reports/live_progress.html` and, when a baseline is found, copying the
selected vLLM benchmark JSON to `reports/baseline_target.json`. It should not
write generated HTML into `workspace/`, `logs/`, `bundles/`, or `exp_env/`
top-level directories.

When adding new widgets to the live page, keep them self-contained in
`live_progress.html` and read from existing JSON artifacts where possible.
Prefer adding stable fields to `report.json` or `round_summary.json` over
scraping logs in browser JavaScript.

## Useful defaults

- For most runs: `--live-monitor --live-monitor-open`.
- Use a fixed port to avoid collisions, for example `--live-monitor-port 62187`.

## Why this matters

The monitor summarizes round status, passing/failing state, baseline target,
and latency summaries from `report.json` in one page so you can track progress
without polling logs manually.
